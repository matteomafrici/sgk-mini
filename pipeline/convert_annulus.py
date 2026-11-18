#!/usr/bin/env python3
"""Probe the VDB and CFD conversion on one accepted annulus case."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from annulus_case import DLL, REPO, Request, sha256
from run_batch import read_json, verify_record

sys.path.insert(0, str(Path(REPO) / "validation"))
from validate_annulus import read_field


def convert(root, case_id, output, dll):
    index = read_json(root / "index.json")
    if index["manifest_sha256"] != sha256(root / "manifest.json"):
        raise ValueError("batch index does not match the frozen manifest")
    entry = next((row for row in index["cases"] if row["physical_case_id"] == case_id), None)
    if entry is None or entry["status"] != "ok":
        raise ValueError(f"{case_id} is not an accepted physical case")
    record_path = root / entry["record"]
    record = read_json(record_path)
    point = next(p for p in read_json(root / "manifest.json")["cases"] if p["case_id"] == case_id)
    request = Request.from_dict(point | {"voxel_size_mm": entry["voxel_size_mm"]})
    record = verify_record(record_path, request)
    if record["status"] != "ok" or record["case_id"] != entry["selected_case_id"]:
        raise ValueError("selected attempt does not match the batch index")

    case_dir = record_path.parent
    shape = record["geometry"]["physical"]
    report = record["reference"]["report"]
    time_dir = Path("openfoam") / report["time_dir"]
    vdb_path = Path("geometry") / f"{record['case_id']}.vdb"
    for name in (vdb_path, *(time_dir / field for field in ("C", "U", "V", "p"))):
        if name.as_posix() not in record["artifacts"]:
            raise ValueError(f"accepted artifact is not listed in the manifest: {name}")

    coordinates, velocity, volumes, pressure = [
        read_field(case_dir / time_dir / field) for field in ("C", "U", "V", "p")
    ]
    count = report["mesh"]["cells"]
    if (coordinates.shape, velocity.shape, volumes.shape, pressure.shape) != (
        (count, 3), (count, 3), (count,), (count,),
    ) or np.any(volumes <= 0):
        raise ValueError("field arrays do not match the mesh or contain invalid volumes")

    # Rotate the CFD +x axis onto PicoGK +z. Both positions and vectors use
    # the same right-handed permutation. Positions are still in SI units.
    xyz = coordinates[:, [1, 2, 0]]
    u_xyz = velocity[:, [1, 2, 0]]
    voxel_mm = request.voxel_size_mm
    ro = shape["OuterRadiusMm"]
    ri = shape["InnerRadiusMm"]
    length = shape["LengthMm"]
    extent_mm = ro + 2 * voxel_mm
    grid_mm = [np.linspace(-extent_mm, extent_mm, 48)] * 2 + [
        np.linspace(-2 * voxel_mm, length + 2 * voxel_mm, 32),
    ]
    lattice = np.stack(np.meshgrid(*grid_mm, indexing="ij"), axis=-1)
    outer_node = math.floor(ro / voxel_mm) * voxel_mm
    probes_mm = np.array([
        [0, 0, length / 2],
        [0, (ri + ro) / 2, length / 2],
        [0, extent_mm, length / 2],
        [0, (ri + ro) / 2, length + 2 * voxel_mm],
        [0, outer_node, length / 2],
        [0, outer_node + voxel_mm, length / 2],
    ])
    queries_mm = np.concatenate((probes_mm, xyz * 1000, lattice.reshape(-1, 3)))
    with tempfile.TemporaryDirectory(prefix="sgk-vdb-converter-") as temp:
        work = Path(temp)
        queries, sdf, surface = (work / name for name in ("queries.tsv", "sdf.tsv", "surface.tsv"))
        np.savetxt(queries, queries_mm, delimiter="\t", fmt="%.9g")
        subprocess.run([
            "dotnet", str(dll), "--sample-vdb", str(case_dir / vdb_path), str(voxel_mm),
            str(queries), str(sdf), str(surface),
        ], cwd=dll.parent, check=True)
        samples_mm = np.loadtxt(sdf)
        vertices_mm = np.loadtxt(surface, ndmin=2)

    if samples_mm.shape != (len(queries_mm),) or not np.all(np.isfinite(samples_mm)):
        raise ValueError("VDB returned an invalid signed distance array")
    if vertices_mm.shape[1] != 3 or len(vertices_mm) < 4 or not np.all(np.isfinite(vertices_mm)):
        raise ValueError("VDB returned an invalid surface point cloud")
    if not np.array_equal(np.sign(samples_mm[:4]), [1, -1, 1, 1]):
        raise ValueError(f"incorrect core, wall, exterior or end-cap signs: {samples_mm[:4]}")
    if not math.isclose(samples_mm[5] - samples_mm[4], voxel_mm, rel_tol=.15):
        raise ValueError("native SDF slope at the outer wall disagrees with the voxel pitch")
    if np.max(np.abs(samples_mm)) > voxel_mm + 1e-6:
        raise ValueError("VDB distance exceeds the declared narrow-band clip")
    bounds = np.stack((vertices_mm.min(axis=0), vertices_mm.max(axis=0)))
    expected = np.array([[-ro, -ro, 0], [ro, ro, length]])
    if np.max(np.abs(bounds - expected)) > 2 * voxel_mm:
        raise ValueError("VDB surface bounds disagree with the reconstructed annulus")

    start = len(probes_mm)
    q_sdf_mm = samples_mm[start:start + count]
    radial_mm = np.linalg.norm(xyz[:, :2] * 1000, axis=1)
    interior = (
        (radial_mm > ri + 2 * voxel_mm) & (radial_mm < ro - 2 * voxel_mm)
        & (xyz[:, 2] * 1000 > 2 * voxel_mm)
        & (xyz[:, 2] * 1000 < length - 2 * voxel_mm)
    )
    if not np.any(interior) or np.any(q_sdf_mm[interior] >= 0):
        raise ValueError("interior CFD centres do not align with the VDB material")

    output.mkdir(parents=True)
    arrays = output / "sample.npz"
    np.savez_compressed(
        arrays, query_xyz_m=xyz, velocity_m_s=u_xyz, volume_m3=volumes,
        pressure_periodic_pa=pressure * shape["DensityKgPerM3"],
        query_solid_sdf_m=q_sdf_mm * .001, surface_xyz_m=vertices_mm * .001,
        grid_sdf_m=samples_mm[start + count:].reshape(lattice.shape[:3]) * .001,
        grid_x_m=grid_mm[0] * .001, grid_y_m=grid_mm[1] * .001, grid_z_m=grid_mm[2] * .001,
        driving_gradient_pa_m=report["dpL_cfd"],
    )
    with np.load(arrays) as saved:
        factor = 360.0 / report["mesh"]["totalAngleDeg"]
        full_q = float(saved["velocity_m_s"][:, 2] @ saved["volume_m3"]) / (length * .001) * factor
    if not math.isclose(full_q, report["Q_full_field"], rel_tol=1e-7):
        raise ValueError("converted array flow disagrees with the validated CFD field integral")
    flow_error_pct = 100 * abs(full_q / shape["VolumetricFlowRateM3PerS"] - 1)
    if flow_error_pct >= .05:
        raise ValueError("converted array flow misses the 0.05% limit")

    metadata = {
        "schema": "sgk-mini.annulus-conversion-probe.v1",
        "case_id": case_id,
        "attempt_case_id": record["case_id"],
        "split": entry["split"],
        "source_record": str(record_path),
        "source_record_sha256": sha256(record_path),
        "source_vdb_sha256": record["artifacts"][vdb_path.as_posix()],
        "sampler_assembly_sha256": sha256(dll),
        "sample_sha256": sha256(arrays),
        "frame": "PicoGK axes in SI units; OpenFOAM (x,y,z) -> (y,z,x)",
        "sdf": (
            "negative inside the VDB material; the benchmark uses this extent "
            "as the CFD annulus; nearest voxel, clipped to one source voxel"
        ),
        "surface": "native isosurface mesh vertices",
        "query_rows": count,
        "interior_rows_checked": int(interior.sum()),
        "surface_points": len(vertices_mm),
        "grid_shape": list(lattice.shape[:3]),
        "probe_values_mm": samples_mm[:start].tolist(),
        "full_circle_flow_m3_s": full_q,
        "flow_error_pct": flow_error_pct,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", required=True, help="physical case ID in the batch manifest")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dll", type=Path, default=Path(DLL))
    args = parser.parse_args()
    convert(args.root.resolve(), args.case, args.out.resolve(), args.dll.resolve())


if __name__ == "__main__":
    main()
