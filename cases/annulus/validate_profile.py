#!/usr/bin/env python3
"""Validate OpenFOAM axial velocity profile against analytical annular solution."""

import json
import math
import re
import sys

CASE_DIR = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"

# --- 1. Read analytical benchmark ---
with open(f"{CASE_DIR}/../../output/hollow-cylinder.physical-case.json") as f:
    bench = json.load(f)

samples = bench["VelocityProfileSamples"]
Ri = bench["InnerRadiusMm"]
Ro = bench["OuterRadiusMm"]
bench_r = [s["RadiusMm"] for s in samples]
bench_U = [s["AxialVelocityMPerS"] for s in samples]

# --- 2. Parse OpenFOAM cell centres and U field ---
def read_foam_vector_field(path):
    """Read OpenFOAM nonuniform List<vector> file. Returns list of (x,y,z) tuples."""
    with open(path) as f:
        text = f.read()
    # Find the internalField block
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    if not m:
        raise ValueError("Could not parse internalField from " + path)
    n = int(m.group(1))
    body = m.group(2)
    # Parse vector tuples (x y z)
    vals = []
    for triple in re.findall(r"\(([^)]+)\)", body):
        parts = triple.strip().split()
        vals.append(tuple(float(p) for p in parts))
    if len(vals) != n:
        raise ValueError(f"Expected {n} values, got {len(vals)}")
    return vals

centres = read_foam_vector_field(f"{CASE_DIR}/200/C")
U_vals = read_foam_vector_field(f"{CASE_DIR}/200/U")

# --- 3. Filter cells near mid-plane (θ≈0, z>0) and mid-length (x≈0.025) ---
# The sector is centered on +z axis, half-angle 15°.
# We want cells in the innermost angular layer (closest to θ=0).
# The mesh has 3 cells in angular direction.
# The θ=0 plane is at the center; we pick cells with y ≈ 0 and z > 0.

R_EPS = 0.0005  # mm radial tolerance
X_TARGET = 25.0  # mm (mid-length)
X_EPS = 0.5     # mm

profiles = {}  # r_mm -> list of Ux_mps

for (cx, cy, cz), (Ux, Uy, Uz) in zip(centres, U_vals):
    cx_mm = cx * 1000
    cy_mm = cy * 1000
    cz_mm = cz * 1000
    r_mm = math.sqrt(cy_mm**2 + cz_mm**2)

    # Filter: near mid-length, y ≈ 0 (center of sector), within annulus
    if abs(cx_mm - X_TARGET) > X_EPS:
        continue
    if abs(cy_mm) > 0.2:  # within ~0.2 mm of the y=0 plane
        continue
    if r_mm < Ri - 0.1 or r_mm > Ro + 0.1:
        continue

    # Bucket by radius
    key = round(r_mm, 4)
    profiles.setdefault(key, []).append(Ux)

# Average bucket values and sort by radius
radii = sorted(profiles.keys())
cfd_r = []
cfd_U = []
for r in radii:
    vals = profiles[r]
    cfd_r.append(r)
    cfd_U.append(sum(vals) / len(vals))

print(f"Extracted {len(cfd_r)} radial sample points from CFD")

# --- 4. Interpolate benchmark to CFD radii for comparison ---
def interpolate(x_target, x_data, y_data):
    if x_target <= x_data[0]:
        return y_data[0]
    if x_target >= x_data[-1]:
        return y_data[-1]
    for i in range(len(x_data) - 1):
        if x_data[i] <= x_target <= x_data[i + 1]:
            t = (x_target - x_data[i]) / (x_data[i + 1] - x_data[i])
            return y_data[i] + t * (y_data[i + 1] - y_data[i])
    return y_data[-1]

max_err = 0.0
max_err_r = 0.0
abs_errs = []
rel_errs = []

print("\n--- Radial Profile: CFD vs Analytical ---")
print(f"{'r (mm)':>10s}  {'U_CFD (m/s)':>12s}  {'U_bench (m/s)':>14s}  {'Abs err':>10s}  {'Rel err':>10s}")
print("-" * 62)

for r, u_cfd in zip(cfd_r, cfd_U):
    u_bench = interpolate(r, bench_r, bench_U)
    abs_err = abs(u_cfd - u_bench)
    rel_err = abs_err / u_bench * 100 if u_bench > 1e-10 else 0
    abs_errs.append(abs_err)
    rel_errs.append(rel_err)
    if abs_err > max_err:
        max_err = abs_err
        max_err_r = r
    print(f"{r:10.4f}  {u_cfd:12.8f}  {u_bench:14.10f}  {abs_err:10.2e}  {rel_err:10.4f}")

mean_abs = sum(abs_errs) / len(abs_errs)
mean_rel = sum(rel_errs) / len(rel_errs)

print(f"\n--- Summary ---")
print(f"Sample points:        {len(cfd_r)}")
print(f"Max abs error:        {max_err:.3e} m/s at r={max_err_r:.4f} mm")
print(f"Mean abs error:       {mean_abs:.3e} m/s")
print(f"Mean rel error:       {mean_rel:.4f} %")
print(f"Benchmark max vel:    {bench['MaxVelocityMPerS']:.6f} m/s")
print(f"Benchmark max vel r:  {bench['MaxVelocityRadiusMm']:.4f} mm")
# Find CFD max vel
max_idx = cfd_U.index(max(cfd_U))
print(f"CFD max vel:          {cfd_U[max_idx]:.8f} m/s at r={cfd_r[max_idx]:.4f} mm")

PASS_THRESHOLD = 0.01  # 1% mean relative error
if mean_rel < PASS_THRESHOLD:
    print(f"\n*** VALIDATION PASSED *** (mean rel error {mean_rel:.4f}% < {PASS_THRESHOLD}%)")
    sys.exit(0)
else:
    print(f"\n*** VALIDATION FAILED *** (mean rel error {mean_rel:.4f}% >= {PASS_THRESHOLD}%)")
    sys.exit(1)
