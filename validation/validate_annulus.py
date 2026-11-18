#!/usr/bin/env python3
"""Reproducible CFD validation: annular Poiseuille flow in a 2D wedge.

Compares OpenFOAM `simpleFoam` against the closed-form analytical solution for
steady, fully developed, laminar axial flow in a concentric annulus.

The reference case is a thin axisymmetric wedge with one cell in the tangential
direction and axial periodicity. The wedge is a *finite* angular sector, so its
cross-section is a polygon, not a circle: the flow area is smaller than the ideal
annulus by `sin(theta)/theta`. That geometric defect is measured from the mesh
cell volumes and reported; it is not corrected away.

Inputs (defaults, overridable on the command line):
  --case DIR        OpenFOAM case directory
  --benchmark FILE  physical record written by SGK.Geometry
  --log FILE        simpleFoam log
  --flux-log FILE   log produced by the flowRatePatch function objects

Options:
  --check           exit non-zero if a criterion fails
  --check-inputs    only verify the case inputs against the record
  --json FILE       write a machine-readable report
"""

import argparse
import json
import math
import os
import re
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CASE = os.path.join(REPO, "validation", "openfoam", "annulus_cyclic")
DEFAULT_BENCH = os.path.join(REPO, "output", "hollow-cylinder.physical-case.json")

# Acceptance criteria for the reference case. These are fixed in
# docs/pilot-checks.md before the results were seen. They are engineering
# targets for a second-order finite-volume solution on this mesh, not a claim
# about a theoretical floor.
TOL = {
    "umax_pct": 1.0,
    "dpL_pct": 0.5,
    "q_pct": 0.05,
    "mean_pct": 1.0,
    "max_pct": 2.5,
    "imbalance": 1.0e-6,
    "transverse": 1.0e-6,
    "stability": 1.0e-5,
}

EPS_REL = 1.0e-6


# ---------------------------------------------------------------------------
# Reading and parsing
# ---------------------------------------------------------------------------


def _strip_comment(line):
    return line.split("//")[0]


def read_scalar_dict(path, names):
    """Return the values of top-level `name value;` entries.

    blockMeshDict and transportProperties use this form for the numbers that
    connect the case to the geometry record. Values produced by `#eval{}` are
    not literal inputs and are intentionally not returned.
    """
    values = {}

    with open(path) as f:
        for line in f:
            stripped = _strip_comment(line).strip()
            match = re.match(r"^([A-Za-z_]\w*)\s+([-+0-9.eE]+)\s*;$", stripped)
            if match and match.group(1) in names:
                values[match.group(1)] = float(match.group(2))

    return values


def read_vector_dict(path, name):
    """Return a vector entry such as `Ubar (a b c);` as a list of floats."""
    with open(path) as f:
        text = "\n".join(_strip_comment(line) for line in f)

    matches = re.findall(rf"\b{name}\s*\(\s*([^)]*)\)\s*;", text)
    if not matches:
        raise SystemExit(f"{name} not found in {path}")

    components = [float(x) for x in matches[-1].split()]
    if len(components) != 3:
        raise SystemExit(f"{name} in {path} is not a three-component vector")

    return components


def require_finite(value, name):
    """Reject NaN and infinities before they can silently compare as 'passing'."""
    if isinstance(value, (list, tuple, np.ndarray)):
        for i, item in enumerate(value):
            require_finite(item, f"{name}[{i}]")
        return
    if not math.isfinite(float(value)):
        raise SystemExit(f"Non-finite value for {name}: {value}")


def read_field(path):
    """Read a nonuniform OpenFOAM field and reject non-finite entries."""
    with open(path) as f:
        text = f.read()

    is_vector = "volVectorField" in text
    kind = r"List<vector>" if is_vector else r"List<scalar>"
    match = re.search(
        rf"internalField\s+nonuniform\s+{kind}\s+(\d+)\s*\(([\s\S]*?)\)\s*;",
        text,
    )
    if match is None:
        if re.search(r"internalField\s+uniform", text):
            raise SystemExit(f"{path}: field is still uniform (solver did not write values)")
        raise SystemExit(f"{path}: could not parse a nonuniform field")

    count = int(match.group(1))
    body = match.group(2)

    if is_vector:
        values = np.array(
            [tuple(float(x) for x in item.split()) for item in re.findall(r"\(([^)]+)\)", body)]
        )
    else:
        values = np.array([float(x) for x in body.split()])

    if len(values) != count:
        raise SystemExit(f"{path}: expected {count} values, parsed {len(values)}")
    if not np.all(np.isfinite(values)):
        bad = int(np.argwhere(~np.isfinite(values))[0][0])
        raise SystemExit(f"{path}: non-finite value at index {bad}")

    return values


def read_mesh_metadata(case_dir):
    """Read the literal mesh inputs and the dimensions used by the extraction."""
    block_mesh = os.path.join(case_dir, "system", "blockMeshDict")
    values = read_scalar_dict(
        block_mesh,
        {"Ri", "Ro", "L", "halfAngle", "nX", "nR1", "nR2", "nAng"},
    )

    required = ("Ri", "Ro", "L", "halfAngle", "nX", "nR1", "nR2", "nAng")
    missing = [name for name in required if name not in values]
    if missing:
        raise SystemExit(f"{block_mesh}: missing literal(s): {', '.join(missing)}")

    for name in required:
        require_finite(values[name], name)

    meta = {
        "Ri": values["Ri"],
        "Ro": values["Ro"],
        "L": values["L"],
        "halfAngleDeg": values["halfAngle"],
        "nX": int(values["nX"]),
        "nR1": int(values["nR1"]),
        "nR2": int(values["nR2"]),
        "nAng": int(values["nAng"]),
    }

    if meta["Ri"] <= 0 or meta["Ro"] <= meta["Ri"]:
        raise SystemExit(f"{block_mesh}: invalid radii Ri={meta['Ri']}, Ro={meta['Ro']}")
    if meta["L"] <= 0 or meta["halfAngleDeg"] <= 0:
        raise SystemExit(f"{block_mesh}: invalid length or wedge angle")
    if meta["nX"] <= 0 or meta["nR1"] <= 0 or meta["nR2"] <= 0 or meta["nAng"] <= 0:
        raise SystemExit(f"{block_mesh}: cell counts must be positive")

    meta["totalAngleDeg"] = 2.0 * meta["halfAngleDeg"]
    meta["cells"] = meta["nX"] * (meta["nR1"] + meta["nR2"]) * meta["nAng"]

    return meta


def read_flux_log(path):
    """Parse the sums written by the flowRatePatch function objects.

    The two cyclic patches are the two axial ends of the periodic domain. Their
    signed fluxes must be equal and opposite; either one is the sector flow.
    """
    if not os.path.isfile(path):
        raise SystemExit(
            f"Flux log not found: {path}\nRun validation/run_annulus.sh first."
        )

    with open(path) as f:
        text = f.read()

    fluxes = {}
    areas = {}

    for patch, value in re.findall(r"sum\((\w+)\) of phi\s*=\s*([-+0-9.eE]+)", text):
        fluxes[patch] = float(value)

    # flowRatePatch prints the area of the patch just above the flux.
    for block in text.split("write:")[1:]:
        name = re.search(r"flowRatePatch\(name=(\w+)\)", block)
        area = re.search(r"total area\s*=\s*([-+0-9.eE]+)", block)
        if name and area:
            areas[name.group(1)] = float(area.group(1))

    if "cyclicLeft" not in fluxes or "cyclicRight" not in fluxes:
        raise SystemExit(
            f"{path}: expected sums for cyclicLeft and cyclicRight, found {sorted(fluxes)}"
        )

    for patch, value in fluxes.items():
        require_finite(value, f"flux {patch}")

    return fluxes, areas


def read_solver_log(path, meta):
    """Read residuals, continuity, iteration count and pressure gradient history."""
    if not os.path.isfile(path):
        raise SystemExit(f"Solver log not found: {path}")

    time = 0
    last = {"Ux": None, "Uy": None, "Uz": None, "p": None}
    last_continuity = None
    gradients = {}
    times_seen = []

    with open(path) as f:
        for line in f:
            match = re.match(r"^Time = (\d+)", line)
            if match:
                time = int(match.group(1))
                times_seen.append(time)
                continue

            match = re.search(
                r"Solving for (Ux|Uy|Uz|p), Initial residual = ([-+0-9.eE]+)", line
            )
            if match:
                require_finite(match.group(2), f"residual {match.group(1)}")
                last[match.group(1)] = float(match.group(2))
                continue

            match = re.search(
                r"time step continuity errors\s*:\s*sum local = ([-+0-9.eE]+),\s*"
                r"global = ([-+0-9.eE]+),\s*cumulative = ([-+0-9.eE]+)",
                line,
            )
            if match:
                require_finite(match.group(2), "continuity global")
                last_continuity = float(match.group(2))
                continue

            match = re.search(r"pressure gradient = ([-+0-9.eE]+)", line)
            if match:
                require_finite(match.group(1), "pressure gradient")
                gradients[time] = float(match.group(1))

    if not times_seen:
        raise SystemExit(f"{path}: no 'Time = N' lines, the solver did not run")

    iterations = times_seen[-1]
    end_time = int(read_scalar_dict(
        os.path.join(os.path.dirname(path), "system", "controlDict"), {"endTime"}
    ).get("endTime", iterations))

    targets = read_residual_targets(os.path.dirname(path))

    return {
        "iterations": iterations,
        "endTime": end_time,
        "stopping_reason": "residual-control" if iterations < end_time else "iteration-limit",
        "residuals": last,
        "continuity_global": last_continuity,
        "pressure_gradient_kinematic": gradients,
        "targets": targets,
    }


def read_residual_targets(case_dir):
    """Read the SIMPLE residualControl targets from fvSolution."""
    path = os.path.join(case_dir, "system", "fvSolution")
    with open(path) as f:
        text = f.read()

    match = re.search(r"residualControl\s*\{([\s\S]*?)\}", text)
    if not match:
        raise SystemExit(f"{path}: residualControl block not found")

    targets = {}
    for name, value in re.findall(r"(\w+)\s+([-+0-9.eE]+)\s*;", match.group(1)):
        targets[name] = float(value)

    if "U" not in targets or "p" not in targets:
        raise SystemExit(f"{path}: residualControl must define U and p")

    return targets


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------


def U_analytical(r, Ri, Ro, dpL, mu):
    """Annular Poiseuille velocity profile, dpL positive in the flow direction."""
    return (dpL / (4.0 * mu)) * (
        Ro * Ro - r * r
        + (Ro * Ro - Ri * Ri) * math.log(r / Ro) / math.log(Ro / Ri)
    )


def extract_profile(case_dir, time_name, meta, centres_time=None):
    """Return x[nX], r_face[nR], ux[nX, nR], p[nX, nR].

    The comparison is done at the radius of the cell *faces* in the radial
    direction, recovered from the cell centre by undoing the chord shortening of
    the angular discretisation. For a cell whose angular extent is `dtheta`, the
    centre sits at `r_face * cos(dtheta/2)`; the analytical profile is evaluated
    at `r_face`, which lies inside [Ri, Ro]. The raw cell-centre radius of the
    innermost cell is *inside* the ideal wall and would be an extrapolation.

    Only the angular layer closest to the axis bisector is used for the profile,
    because its centre is the physical one; the other layers in a multi-cell
    wedge are not used for the profile at all.
    """
    centres_time = centres_time or time_name
    C = read_field(os.path.join(case_dir, centres_time, "C"))
    U = read_field(os.path.join(case_dir, time_name, "U"))
    p_raw = read_field(os.path.join(case_dir, time_name, "p"))

    if len(C) != len(U) or len(C) != len(p_raw):
        raise SystemExit(
            f"{case_dir}: cell count mismatch C={len(C)}, U={len(U)}, p={len(p_raw)}"
        )

    if len(C) != meta["cells"]:
        raise SystemExit(
            f"{case_dir}: mesh has {len(C)} cells but blockMeshDict declares {meta['cells']}"
        )

    x = C[:, 0]
    r_centre = np.hypot(C[:, 1], C[:, 2])
    angle = np.degrees(np.arctan2(C[:, 1], C[:, 2]))

    angle_key = np.round(angle, 6)
    angle0 = angle_key[np.argmin(np.abs(angle_key))]
    layer = angle_key == angle0
    if layer.sum() == 0:
        raise SystemExit(f"{case_dir}: could not identify the central angular layer")

    x_key = np.round(x[layer], 9)
    r_key = np.round(r_centre[layer], 9)
    ux_layer = U[layer, 0]
    p_layer = p_raw[layer]

    x_unique, x_index = np.unique(x_key, return_inverse=True)
    r_unique, r_index = np.unique(r_key, return_inverse=True)

    if len(x_unique) * len(r_unique) != int(layer.sum()):
        raise SystemExit(
            f"{case_dir}: central layer does not form a complete x-r grid "
            f"({len(x_unique)} x {len(r_unique)} != {int(layer.sum())})"
        )

    ux = np.full((len(x_unique), len(r_unique)), np.nan)
    p = np.full((len(x_unique), len(r_unique)), np.nan)
    ux[x_index, r_index] = ux_layer
    p[x_index, r_index] = p_layer

    if not np.all(np.isfinite(ux)) or not np.all(np.isfinite(p)):
        raise SystemExit(f"{case_dir}: the x-r grid has missing or non-finite values")

    # Half-width of one angular cell, in degrees. A cell centred on the sector
    # bisector has its centre at r_face * cos(half width).
    half_width = math.radians(meta["halfAngleDeg"] / meta["nAng"])
    r_face = r_unique / math.cos(half_width)

    if np.any(r_face <= meta["Ri"]) or np.any(r_face >= meta["Ro"]):
        bad = r_face[(r_face <= meta["Ri"]) | (r_face >= meta["Ro"])]
        raise SystemExit(
            f"{case_dir}: comparison radii leave the analytical domain "
            f"[{meta['Ri']}, {meta['Ro']}] m: {bad}"
        )

    return x_unique, r_face, ux, p


def field_volumes(case_dir, time_name):
    """Read the cell volumes written by `postProcess -func writeCellVolumes`."""
    path = os.path.join(case_dir, time_name, "V")
    if not os.path.isfile(path):
        raise SystemExit(
            f"Cell volumes not found: {path}\n"
            "Run validation/run_annulus.sh (it writes them after solving)."
        )
    return read_field(path)


# ---------------------------------------------------------------------------
# Input guards
# ---------------------------------------------------------------------------


def load_benchmark(path):
    if not os.path.isfile(path):
        raise SystemExit(
            f"Benchmark not found: {path}\n"
            "Run the geometry stage first:  dotnet run --project src/SGK.Geometry/ -- --auto-exit"
        )

    with open(path) as f:
        bench = json.load(f)

    for name in (
        "InnerRadiusMm", "OuterRadiusMm", "LengthMm", "DensityKgPerM3",
        "DynamicViscosityPaS", "VolumetricFlowRateM3PerS", "MeanVelocityMPerS",
        "PressureGradientPaPerM", "MaxVelocityMPerS", "ReynoldsNumber",
        "CrossSectionAreaMm2",
    ):
        if name not in bench:
            raise SystemExit(f"{path}: missing field {name}")
        require_finite(bench[name], name)

    # The record must be internally consistent before it is used as a reference.
    Ri = bench["InnerRadiusMm"] * 1.0e-3
    Ro = bench["OuterRadiusMm"] * 1.0e-3
    area = math.pi * (Ro * Ro - Ri * Ri)
    expected_area_mm2 = area * 1.0e6
    if abs(bench["CrossSectionAreaMm2"] - expected_area_mm2) > 1.0e-6 * expected_area_mm2:
        raise SystemExit(
            f"{path}: cross-section area {bench['CrossSectionAreaMm2']} does not match "
            f"pi*(Ro^2-Ri^2) = {expected_area_mm2}"
        )

    expected_mean = bench["VolumetricFlowRateM3PerS"] / area
    if abs(bench["MeanVelocityMPerS"] - expected_mean) > EPS_REL * expected_mean:
        raise SystemExit(
            f"{path}: mean velocity {bench['MeanVelocityMPerS']} does not match Q/area {expected_mean}"
        )

    dh = 2.0 * (Ro - Ri)
    expected_re = bench["DensityKgPerM3"] * bench["MeanVelocityMPerS"] * dh / bench["DynamicViscosityPaS"]
    if abs(bench["ReynoldsNumber"] - expected_re) > EPS_REL * expected_re:
        raise SystemExit(
            f"{path}: Reynolds {bench['ReynoldsNumber']} does not match {expected_re}"
        )

    if bench["ReynoldsNumber"] >= 2000.0:
        raise SystemExit(f"{path}: flow is not laminar (Re={bench['ReynoldsNumber']})")

    return bench


def check_inputs(case_dir, bench_path, verbose=True):
    """Verify every literal number connecting the record to the solver.

    This is the failure mode the project already paid for once: a stale `Ubar`
    shifted every metric without any other symptom. Radii, length, viscosity and
    the full imposed velocity vector are checked before the mesh is built.
    """
    bench = load_benchmark(bench_path)
    meta = read_mesh_metadata(case_dir)

    problems = []

    def compare(name, actual, expected, rel_tol=EPS_REL):
        if abs(actual - expected) > rel_tol * max(abs(expected), 1.0e-30):
            problems.append(
                f"{name}: case says {actual:.12g}, record says {expected:.12g} "
                f"(relative difference {abs(actual - expected) / max(abs(expected), 1.0e-30):.2e})"
            )

    case_meta_path = os.path.join(case_dir, "case.json")
    if not os.path.isfile(case_meta_path):
        problems.append(f"case identity file missing: {case_meta_path}")
    else:
        with open(case_meta_path) as f:
            case_meta = json.load(f)
        if case_meta.get("CaseId") != bench["CaseId"]:
            problems.append(
                f"case id: case directory says {case_meta.get('CaseId')!r}, "
                f"record says {bench['CaseId']!r} (stale or swapped case)"
            )

    compare("Ri", meta["Ri"], bench["InnerRadiusMm"] * 1.0e-3)
    compare("Ro", meta["Ro"], bench["OuterRadiusMm"] * 1.0e-3)
    compare("L", meta["L"], bench["LengthMm"] * 1.0e-3)

    transport = os.path.join(case_dir, "constant", "transportProperties")
    nu = read_scalar_dict(transport, {"nu"}).get("nu")
    if nu is None:
        problems.append(f"nu not found in {transport}")
    else:
        compare("nu", nu, bench["DynamicViscosityPaS"] / bench["DensityKgPerM3"])

    fv_options = os.path.join(case_dir, "constant", "fvOptions")
    ubar = read_vector_dict(fv_options, "Ubar")
    compare("Ubar x", ubar[0], bench["MeanVelocityMPerS"])
    for i, axis in ((1, "y"), (2, "z")):
        if abs(ubar[i]) > 1.0e-12:
            problems.append(
                f"Ubar {axis} = {ubar[i]}, expected 0: the analytical case has no "
                "transverse mean velocity"
            )

    if problems:
        raise SystemExit(
            "CFD case and geometry record disagree:\n  "
            + "\n  ".join(problems)
            + "\n\nRegenerate system/blockMeshDict, constant/fvOptions and "
            "constant/transportProperties from the record, or re-run the geometry "
            "stage if the requested case changed."
        )

    if verbose:
        print(
            "CFD case inputs match the geometry record: "
            f"Ri={meta['Ri'] * 1e3:.6f} mm, Ro={meta['Ro'] * 1e3:.6f} mm, "
            f"L={meta['L'] * 1e3:.6f} mm, nu={nu:.9e} m2/s, "
            f"Ubar=({ubar[0]:.9f}, {ubar[1]:.0f}, {ubar[2]:.0f}) m/s"
        )

    return meta, bench


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def latest_time_dir(case_dir):
    times = []
    for name in os.listdir(case_dir):
        if re.fullmatch(r"\d+(\.\d+)?", name):
            times.append((float(name), name))
    return max(times)[1] if times else None


def saved_time_dirs(case_dir):
    times = []
    for name in os.listdir(case_dir):
        if re.fullmatch(r"\d+(\.\d+)?", name) and name != "0":
            times.append((float(name), name))
    return [name for _, name in sorted(times)]


def relative_change(a, b):
    scale = max(abs(a), abs(b), 1.0e-30)
    return abs(a - b) / scale


def build_report(case_dir, bench_path, log_path, flux_path):
    meta, bench = check_inputs(case_dir, bench_path, verbose=False)

    Ri = bench["InnerRadiusMm"] * 1.0e-3
    Ro = bench["OuterRadiusMm"] * 1.0e-3
    dpL = bench["PressureGradientPaPerM"]
    mu = bench["DynamicViscosityPaS"]
    rho = bench["DensityKgPerM3"]
    Umax_b = bench["MaxVelocityMPerS"]
    Q_b = bench["VolumetricFlowRateM3PerS"]

    times = saved_time_dirs(case_dir)
    if not times:
        raise SystemExit(
            f"No solver time directories in {case_dir}.\n"
            "Run validation/run_annulus.sh first."
        )

    time_name = times[-1]
    x, r_face, ux, p = extract_profile(case_dir, time_name, meta)

    volumes = field_volumes(case_dir, time_name)
    if len(volumes) != len(ux[0]) * len(x) * meta["nAng"]:
        raise SystemExit(
            f"{case_dir}: volume field has {len(volumes)} cells, expected "
            f"{len(x) * len(r_face) * meta['nAng']}"
        )

    U_all = read_field(os.path.join(case_dir, time_name, "U"))
    ux_all = U_all[:, 0]
    transverse = np.hypot(U_all[:, 1], U_all[:, 2])

    q_sector_field = float(np.sum(ux_all * volumes) / meta["L"])
    area_mesh_sector = float(np.sum(volumes) / meta["L"])
    full_circle = 2.0 * math.pi / math.radians(meta["totalAngleDeg"])
    q_full_field = q_sector_field * full_circle

    area_ideal_sector = 0.5 * math.radians(meta["totalAngleDeg"]) * (Ro * Ro - Ri * Ri)
    area_defect_pct = 100.0 * (area_mesh_sector - area_ideal_sector) / area_ideal_sector

    fluxes, patch_areas = read_flux_log(flux_path)
    q_left = fluxes["cyclicLeft"]
    q_right = fluxes["cyclicRight"]
    imbalance = (q_left + q_right) / max(abs(q_left), abs(q_right))
    q_full_native = q_right * full_circle

    solver = read_solver_log(log_path, meta)
    dpL_cfd = solver["pressure_gradient_kinematic"].get(
        int(float(time_name)), None
    )
    if dpL_cfd is None:
        raise SystemExit(f"{log_path}: no pressure gradient recorded at time {time_name}")
    dpL_cfd *= rho

    i_mid = int(np.argmin(np.abs(x - 0.5 * (x[0] + x[-1]))))
    ua_mid = np.array([U_analytical(rr, Ri, Ro, dpL, mu) for rr in r_face])
    ux_mid = ux[i_mid, :]
    rel_err_pct = np.abs(ux_mid - ua_mid) / Umax_b * 100.0

    # Convergence and stability. Reaching endTime is not convergence.
    last_two = times[-2:] if len(times) >= 2 else times
    stability = {}
    if len(last_two) >= 2:
        _, _, ux_prev, _ = extract_profile(
            case_dir, last_two[0], meta, centres_time=time_name
        )
        U_prev = read_field(os.path.join(case_dir, last_two[0], "U"))
        q_prev = float(np.sum(U_prev[:, 0] * volumes) / meta["L"]) * full_circle
        umax_prev = float(np.max(ux_prev[i_mid, :]))
        umax_now = float(np.max(ux_mid))
        stability["umax_rel"] = relative_change(umax_prev, umax_now)
        stability["q_full_rel"] = relative_change(q_prev, q_full_field)

        dp_prev = solver["pressure_gradient_kinematic"].get(int(float(last_two[0])))
        if dp_prev is not None:
            stability["dpL_rel"] = relative_change(dp_prev * rho, dpL_cfd)
        else:
            stability["dpL_rel"] = None
    else:
        stability = {"umax_rel": None, "q_full_rel": None, "dpL_rel": None}

    max_transverse_ratio = float(np.max(transverse) / Umax_b)

    p_all = read_field(os.path.join(case_dir, time_name, "p"))
    p_field_max_abs = float(np.max(np.abs(p_all)))
    # The physical pressure scale is dpL/rho * L. When the field is negligible
    # against it, the normalized p residual divides by a near-zero denominator
    # and cannot reach the configured target; that is a property of the metric,
    # not of the solution.
    p_field_ratio = p_field_max_abs / (dpL / rho * meta["L"])

    umax_cfd = float(np.max(ux_mid))

    report = {
        "case_dir": os.path.abspath(case_dir),
        "benchmark": os.path.abspath(bench_path),
        "time_dir": time_name,
        "mesh": meta,
        "iterations": solver["iterations"],
        "endTime": solver["endTime"],
        "stopping_reason": solver["stopping_reason"],
        "residuals": solver["residuals"],
        "residual_targets": solver["targets"],
        "continuity_global": solver["continuity_global"],
        "p_field_max_abs": p_field_max_abs,
        "p_field_ratio": p_field_ratio,
        "max_transverse_ratio": max_transverse_ratio,
        "stability": stability,
        "profile_station_x_m": float(x[i_mid]),
        "profile": {
            "mean_pct": float(np.mean(rel_err_pct)),
            "max_pct": float(np.max(rel_err_pct)),
            "rms_pct": float(np.sqrt(np.mean(rel_err_pct ** 2))),
            "cells": int(len(r_face)),
        },
        "umax_cfd": umax_cfd,
        "umax_bench": Umax_b,
        "umax_err_pct": float(abs(umax_cfd - Umax_b) / Umax_b * 100.0),
        "dpL_cfd": float(dpL_cfd),
        "dpL_bench": dpL,
        "dpL_err_pct": float(abs(dpL_cfd - dpL) / dpL * 100.0),
        "Q_left": q_left,
        "Q_right": q_right,
        "Q_imbalance": float(imbalance),
        "Q_full_native": float(q_full_native),
        "Q_full_field": float(q_full_field),
        "Q_bench": Q_b,
        "Q_err_pct": float(abs(q_full_native - Q_b) / Q_b * 100.0),
        "Q_field_err_pct": float(abs(q_full_field - Q_b) / Q_b * 100.0),
        "A_mesh_sector": area_mesh_sector,
        "A_ideal_sector": area_ideal_sector,
        "area_defect_pct": float(area_defect_pct),
        "patch_areas": patch_areas,
    }

    # An independent almost-symmetry check: the field-integrated flow and the
    # native patch flux measure the same quantity through different data.
    report["Q_field_vs_native_pct"] = float(
        abs(q_full_field - q_full_native) / max(abs(q_full_native), 1.0e-30) * 100.0
    )

    for key, value in report.items():
        if isinstance(value, (int, float)):
            require_finite(value, key)

    return report


def evaluate(report):
    """Return a list of (name, passed, detail) criteria."""
    checks = []

    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    # The p residual is only meaningful when the pressure field is not
    # numerically zero. In this periodic case the driving gradient lives in the
    # meanVelocityForce source term and p itself is ~1e-15, so its normalized
    # residual divides by a near-zero denominator. The absolute field magnitude
    # against the physical pressure scale is the honest test.
    p_negligible = report["p_field_ratio"] < 1.0e-9
    p_ok = (
        report["residuals"]["p"] is not None
        and report["residuals"]["p"] < report["residual_targets"]["p"]
    )

    add(
        "Ux residual below target",
        report["residuals"]["Ux"] is not None
        and report["residuals"]["Ux"] < report["residual_targets"]["U"],
        f"{report['residuals']['Ux']} vs {report['residual_targets']['U']}",
    )
    add(
        "p residual below target (or p field negligible)",
        p_ok or p_negligible,
        f"residual {report['residuals']['p']} vs {report['residual_targets']['p']}; "
        f"|p|/(dpL/rho*L) = {report['p_field_ratio']:.3e}"
        + (" (negligible: normalized residual not applicable)" if p_negligible else ""),
    )
    add(
        "transverse velocity negligible",
        report["max_transverse_ratio"] < TOL["transverse"],
        f"max|Uy,Uz|/Umax = {report['max_transverse_ratio']:.3e}",
    )
    add(
        "continuity closed",
        report["continuity_global"] is not None
        and abs(report["continuity_global"]) < TOL["imbalance"] * abs(report["Q_right"]),
        f"global = {report['continuity_global']:.3e} m3/s",
    )
    stable = all(
        value is not None and value < TOL["stability"]
        for value in report["stability"].values()
    )
    add(
        "observables stable",
        stable,
        ", ".join(f"{k}={v:.2e}" if v is not None else f"{k}=n/a"
                  for k, v in report["stability"].items()),
    )
    add(
        "convergence criteria met",
        all(check["passed"] for check in checks),
        f"stopped at {report['iterations']} of {report['endTime']} "
        f"({report['stopping_reason']}); convergence is judged on the residuals "
        "and observables above, not on the stop reason",
    )
    add(
        "conservation",
        abs(report["Q_imbalance"]) < TOL["imbalance"],
        f"imbalance = {report['Q_imbalance']:.3e}",
    )
    add(
        "full-circle flow rate",
        report["Q_err_pct"] < TOL["q_pct"],
        f"{report['Q_err_pct']:.4f} % < {TOL['q_pct']} % "
        f"(native); field integral {report['Q_field_err_pct']:.4f} %",
    )
    add(
        "pressure gradient",
        report["dpL_err_pct"] < TOL["dpL_pct"],
        f"{report['dpL_err_pct']:.4f} % < {TOL['dpL_pct']} %",
    )
    add(
        "peak velocity",
        report["umax_err_pct"] < TOL["umax_pct"],
        f"{report['umax_err_pct']:.4f} % < {TOL['umax_pct']} %",
    )
    add(
        "mean profile error",
        report["profile"]["mean_pct"] < TOL["mean_pct"],
        f"{report['profile']['mean_pct']:.4f} % < {TOL['mean_pct']} %",
    )
    add(
        "max profile error",
        report["profile"]["max_pct"] < TOL["max_pct"],
        f"{report['profile']['max_pct']:.4f} % < {TOL['max_pct']} %",
    )

    return checks


def print_report(report, checks):
    print("=" * 64)
    print("  Annular Poiseuille CFD validation (2D wedge, axial periodic)")
    print("=" * 64)
    print(
        f"  Ri={report['mesh']['Ri'] * 1e3:.4f} mm  "
        f"Ro={report['mesh']['Ro'] * 1e3:.4f} mm  "
        f"wedge={report['mesh']['totalAngleDeg']:.3f} deg  "
        f"cells={report['mesh']['cells']}"
    )
    print(f"  time dir: {report['time_dir']}  ({report['stopping_reason']})")
    print(f"  mesh sector area defect: {report['area_defect_pct']:+.4f} %")
    print()
    print(f"  {'metric':<34s} {'value':>14s}")
    print(f"  {'-' * 34} {'-' * 14}")
    rows = [
        ("profile mean |err|/Umax [%]", report["profile"]["mean_pct"]),
        ("profile max  |err|/Umax [%]", report["profile"]["max_pct"]),
        ("profile rms  |err|/Umax [%]", report["profile"]["rms_pct"]),
        ("peak velocity error [%]", report["umax_err_pct"]),
        ("pressure-gradient error [%]", report["dpL_err_pct"]),
        ("flow-rate error (native) [%]", report["Q_err_pct"]),
        ("flow-rate error (field) [%]", report["Q_field_err_pct"]),
        ("conservation imbalance [1]", report["Q_imbalance"]),
    ]
    for label, value in rows:
        print(f"  {label:<34s} {value:>14.6f}")
    print(
        f"\n  dpL_cfd = {report['dpL_cfd']:.6f} Pa/m "
        f"(bench {report['dpL_bench']:.6f})"
    )
    print(
        f"  Q_native = {report['Q_full_native']:.9e} m3/s, "
        f"Q_field = {report['Q_full_field']:.9e} m3/s "
        f"(bench {report['Q_bench']:.9e})"
    )

    failures = [c for c in checks if not c["passed"]]
    print()
    if failures:
        print("  CHECKS FAILED:")
        for check in failures:
            print(f"    - {check['name']}: {check['detail']}")
    else:
        print("  ALL CHECKS PASSED.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--benchmark", default=DEFAULT_BENCH)
    parser.add_argument("--log", default=None)
    parser.add_argument("--flux-log", default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-inputs", action="store_true")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    case_dir = os.path.abspath(args.case)
    bench_path = os.path.abspath(args.benchmark)
    log_path = args.log or os.path.join(case_dir, "log.simpleFoam")
    flux_path = args.flux_log or os.path.join(case_dir, "log.flux")

    if args.check_inputs:
        check_inputs(case_dir, bench_path)
        return 0

    report = build_report(case_dir, bench_path, log_path, flux_path)
    checks = evaluate(report)
    print_report(report, checks)

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"report": report, "checks": checks}, f, indent=2)
        print(f"\n  report written: {args.json}")

    if args.check and not all(c["passed"] for c in checks):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
