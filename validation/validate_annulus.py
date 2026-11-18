#!/usr/bin/env python3
"""Reproducible CFD validation: annular Poiseuille flow (cyclic periodic).

Compares OpenFOAM `simpleFoam` against the closed-form analytical solution
for steady, fully developed, laminar axial flow in a concentric annulus.

Inputs (all paths relative to the repository root):
  - case:      validation/openfoam/annulus_cyclic/
  - benchmark: output/hollow-cylinder.physical-case.json  (written by SGK.Geometry)
  - solver log: validation/openfoam/annulus_cyclic/log.simpleFoam

Run via validation/run_annulus.sh (which sets up the OpenFOAM environment
and runs blockMesh + simpleFoam first).

Options:
  --check   exit non-zero if a metric exceeds its acceptance threshold.
"""

import json
import math
import os
import re
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE = os.path.join(REPO, "validation", "openfoam", "annulus_cyclic")
BENCH = os.path.join(REPO, "output", "hollow-cylinder.physical-case.json")
LOG = os.path.join(CASE, "log.simpleFoam")

# Mesh definition of the case (must match system/blockMeshDict).
NX, NR1, NR2, NANG = 80, 50, 50, 3

# Acceptance thresholds (used only with --check).
TOL = {"umax_pct": 1.0, "dpl_pct": 5.0, "q_pct": 2.0, "mean_pct": 5.0}


def U_analytical(r, Ri, Ro, dpL, mu):
    """Annular Poiseuille velocity profile (same formula as the C# code)."""
    return (dpL / (4.0 * mu)) * (
        Ro * Ro - r * r
        + (Ro * Ro - Ri * Ri) * math.log(r / Ro) / math.log(Ro / Ri)
    )


def read_field(path):
    with open(path) as f:
        text = f.read()
    is_vec = "volVectorField" in text
    if is_vec:
        m = re.search(
            r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;",
            text,
        )
    else:
        m = re.search(
            r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([\s\S]*?)\)\s*;",
            text,
        )
    if m is None:
        raise RuntimeError(f"Could not parse nonuniform field in {path}")
    n, body = int(m.group(1)), m.group(2)
    if is_vec:
        vals = [
            tuple(float(x) for x in t.strip().split())
            for t in re.findall(r"\(([^)]+)\)", body)
        ]
    else:
        vals = [float(x) for x in body.strip().split()]
    if len(vals) != n:
        raise RuntimeError(f"{path}: expected {n} values, got {len(vals)}")
    return vals


def latest_time_dir(case_dir):
    times = []
    for name in os.listdir(case_dir):
        if re.fullmatch(r"\d+(\.\d+)?", name):
            times.append((float(name), name))
    if not times:
        return None
    return max(times)[1]


def extract_profile(case_dir, time_name, rho):
    """Return x[nX], r[NR1+NR2], ux[nX, NR1+NR2], p[nX].

    Extracted at the middle angular layer (k=1). Block 1 (inner) covers
    r=Ri..Rmid, block 2 (outer) covers r=Rmid..Ro.
    """
    C = read_field(f"{case_dir}/{time_name}/C")
    U = read_field(f"{case_dir}/{time_name}/U")
    p_raw = read_field(f"{case_dir}/{time_name}/p")

    b1 = NX * NR1 * NANG
    nj = NR1 + NR2
    x = np.zeros(NX)
    r = np.zeros(nj)
    ux = np.zeros((NX, nj))
    p = np.zeros(NX)

    for j in range(NR1):
        for i in range(NX):
            idx = 1 * NR1 * NX + j * NX + i
            x[i] = C[idx][0]
            r[j] = math.hypot(C[idx][1], C[idx][2])
            ux[i, j] = U[idx][0]

    for j in range(NR2):
        for i in range(NX):
            idx = b1 + 1 * NR2 * NX + j * NX + i
            r[NR1 + j] = math.hypot(C[idx][1], C[idx][2])
            ux[i, NR1 + j] = U[idx][0]

    for i in range(NX):
        idx = 1 * NR1 * NX + 12 * NX + i
        p[i] = p_raw[idx] * rho

    return x, r, ux, p


def Q_from_ux(ux, r):
    """Integrate ux over the cross-section with the midpoint rule."""
    nj = NR1 + NR2
    r_mid_block = (r[NR1 - 1] + r[NR1]) / 2.0
    r_edges = np.zeros(nj + 1)
    r_edges[0] = r[0]
    for j in range(1, NR1):
        r_edges[j] = (r[j - 1] + r[j]) / 2.0
    r_edges[NR1] = r_mid_block
    for j in range(NR1 + 1, nj):
        r_edges[j] = (r[j - 1] + r[j]) / 2.0
    r_edges[nj] = r[-1]
    areas = np.pi * (r_edges[1:] ** 2 - r_edges[:-1] ** 2)
    return np.array([np.sum(ux[i, :] * areas) for i in range(NX)])


def solver_dpL_from_log(log_path, rho):
    """Read the meanVelocityForce pressure gradient from the solver log."""
    if not os.path.isfile(log_path):
        raise RuntimeError(
            f"Solver log not found: {log_path}\n"
            "Run validation/run_annulus.sh first."
        )
    with open(log_path) as f:
        matches = re.findall(r"pressure gradient\s*=\s*([0-9.eE+-]+)", f.read())
    if not matches:
        raise RuntimeError(f"No 'pressure gradient' line in {log_path}")
    return float(matches[-1]) * rho


def check_mesh_radii(Ri_bench, Ro_bench, tol_rel=1e-6):
    """The mesh carries its radii as literal numbers; the record carries the radii
    reconstructed from the voxel geometry. If they drift apart, the solver is
    computing a different geometry than the record describes, and the comparison
    silently compares two different problems."""
    mesh_dict = os.path.join(CASE, "system", "blockMeshDict")
    values = {}

    with open(mesh_dict) as f:
        for line in f:
            stripped = line.split("//")[0].strip().rstrip(";")
            parts = stripped.split(None, 1)
            if len(parts) == 2 and parts[0] in ("Ri", "Ro"):
                values[parts[0]] = float(parts[1])

    problems = []
    for name, bench in (("Ri", Ri_bench), ("Ro", Ro_bench)):
        if name not in values:
            problems.append(f"{name} not found in {mesh_dict}")
            continue
        rel = abs(values[name] - bench) / bench
        if rel > tol_rel:
            problems.append(
                f"{name} in blockMeshDict = {values[name]:.9f} m, benchmark record "
                f"says {bench:.9f} m (relative difference {rel:.2e})"
            )

    if problems:
        raise SystemExit(
            "Mesh and geometry record disagree:\n  "
            + "\n  ".join(problems)
            + "\n\nUpdate system/blockMeshDict from output/hollow-cylinder.physical-case.json,"
            "\nor re-run the geometry stage if the voxel size changed."
        )


def main():
    check = "--check" in sys.argv

    if not os.path.isfile(BENCH):
        raise SystemExit(
            f"Benchmark not found: {BENCH}\n"
            "Run the geometry stage first:  dotnet run --project src/SGK.Geometry/ -- --auto-exit"
        )

    with open(BENCH) as f:
        bench = json.load(f)

    Ri = bench["InnerRadiusMm"] / 1000.0
    Ro = bench["OuterRadiusMm"] / 1000.0
    dpL = bench["PressureGradientPaPerM"]
    mu = bench["DynamicViscosityPaS"]
    rho = bench["DensityKgPerM3"]
    Umax_b = bench["MaxVelocityMPerS"]
    Q_b = bench["VolumetricFlowRateM3PerS"]

    check_mesh_radii(Ri, Ro)

    time_name = latest_time_dir(CASE)
    if time_name is None or time_name == "0":
        raise SystemExit(
            f"No solver time directories in {CASE}.\n"
            "Run validation/run_annulus.sh first."
        )

    x, r, ux, p = extract_profile(CASE, time_name, rho)
    sidx = np.argsort(r)
    r_s, ux_s = r[sidx], ux[:, sidx]

    Q_prof = Q_from_ux(ux_s, r_s)
    i_mid = int(np.argmin(np.abs(x - 0.025)))

    ua_mid = np.array([U_analytical(rr, Ri, Ro, dpL, mu) for rr in r_s])
    ux_mid = ux_s[i_mid, :]
    rel_err_pct = np.abs(ux_mid - ua_mid) / Umax_b * 100.0

    dpL_cfd = solver_dpL_from_log(LOG, rho)

    results = {
        "time_dir": time_name,
        "mean_pct": float(np.mean(rel_err_pct)),
        "max_pct": float(np.max(rel_err_pct)),
        "rms_pct": float(np.sqrt(np.mean(rel_err_pct**2))),
        "umax_err_pct": float(abs(np.max(ux_mid) - Umax_b) / Umax_b * 100.0),
        "dpL_err_pct": float(abs(dpL_cfd - dpL) / dpL * 100.0),
        "Q_err_pct": float(abs(np.mean(Q_prof[-20:]) - Q_b) / Q_b * 100.0),
        "dpL_cfd": float(dpL_cfd),
    }

    print("=" * 56)
    print("  Annular Poiseuille CFD validation (cyclic periodic)")
    print("=" * 56)
    print(f"  Ri={Ri*1000:.4f} mm  Ro={Ro*1000:.4f} mm  Re={bench['ReynoldsNumber']:.2f}")
    print(f"  time dir: {time_name}")
    print(f"  {'metric':<22s} {'value [%]':>12s}")
    print(f"  {'-'*22} {'-'*12}")
    for key, label in [
        ("mean_pct", "mean |err|/Umax"),
        ("max_pct", "max |err|/Umax"),
        ("rms_pct", "rms |err|/Umax"),
        ("umax_err_pct", "Umax error"),
        ("dpL_err_pct", "dpL error"),
        ("Q_err_pct", "flow-rate error"),
    ]:
        print(f"  {label:<22s} {results[key]:>12.4f}")
    print(f"  dpL_cfd = {results['dpL_cfd']:.6f} Pa/m (bench {dpL:.6f})")

    if check:
        failures = []
        if results["umax_err_pct"] > TOL["umax_pct"]:
            failures.append(f"Umax {results['umax_err_pct']:.3f}% > {TOL['umax_pct']}%")
        if results["dpL_err_pct"] > TOL["dpl_pct"]:
            failures.append(f"dpL {results['dpL_err_pct']:.3f}% > {TOL['dpl_pct']}%")
        if results["Q_err_pct"] > TOL["q_pct"]:
            failures.append(f"Q {results['Q_err_pct']:.3f}% > {TOL['q_pct']}%")
        if results["mean_pct"] > TOL["mean_pct"]:
            failures.append(f"mean {results['mean_pct']:.3f}% > {TOL['mean_pct']}%")
        if failures:
            print("\n  CHECK FAILED:")
            for fa in failures:
                print(f"    - {fa}")
            return 1
        print("\n  CHECK PASSED (all metrics within tolerance).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
