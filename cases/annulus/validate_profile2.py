#!/usr/bin/env python3
"""Validate CFD profile against analytical: use structured mesh indexing.

Mesh: 80 (axial) x 30 (radial: 15+15) x 3 (angular). Block ordering:
  Block1: k*1200 + j*80 + i  for i=0..79, j=0..14, k=0..2
  Block2: 3600 + k*1200 + j*80 + i
Middle angular layer: k=1. Mid-length: i=40.
"""
import json, math, re, sys

CASE = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"

with open(f"{CASE}/../../output/hollow-cylinder.physical-case.json") as f:
    bench = json.load(f)

samples = bench["VelocityProfileSamples"]
bench_r = [s["RadiusMm"] for s in samples]
bench_U = [s["AxialVelocityMPerS"] for s in samples]
Ri = bench["InnerRadiusMm"]
Ro = bench["OuterRadiusMm"]
bench_maxU = bench["MaxVelocityMPerS"]
bench_maxR = bench["MaxVelocityRadiusMm"]

def read_field(path):
    with open(path) as f:
        text = f.read()
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    n, body = int(m.group(1)), m.group(2)
    vals = [tuple(float(x) for x in t.strip().split()) for t in re.findall(r"\(([^)]+)\)", body)]
    assert len(vals) == n, f"{len(vals)} != {n}"
    return vals

C = read_field(f"{CASE}/200/C")
U = read_field(f"{CASE}/200/U")

# Structured indexing
nX, nR1, nR2, nAng = 80, 15, 15, 3
nR = nR1 + nR2
b1_cells = nX * nR1 * nAng

# Pick middle angular layer (k=1) at mid-length (i=40)
i_mid = 40
k_mid = 1

cfd_r, cfd_U = [], []

# Block 1: inner wall to mid-radius
for j in range(nR1):
    idx = k_mid * nR1 * nX + j * nX + i_mid
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2) * 1000  # mm
    cfd_r.append(r)
    cfd_U.append(U[idx][0])

# Block 2: mid-radius to outer wall
for j in range(nR2):
    idx = b1_cells + k_mid * nR2 * nX + j * nX + i_mid
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2) * 1000
    cfd_r.append(r)
    cfd_U.append(U[idx][0])

print(f"Extracted {len(cfd_r)} cell-center samples along mid-plane radial line\n")

def interpolate(x, xd, yd):
    if x <= xd[0]: return yd[0]
    if x >= xd[-1]: return yd[-1]
    for i in range(len(xd)-1):
        if xd[i] <= x <= xd[i+1]:
            t = (x - xd[i]) / (xd[i+1] - xd[i])
            return yd[i] + t * (yd[i+1] - yd[i])
    return yd[-1]

print(f"{'r (mm)':>9s}  {'U_CFD':>11s}  {'U_bench':>13s}  {'Err abs':>10s}  {'Err rel%':>9s}")
print("-" * 58)
max_err = 0.0
sum_rel = 0.0
for r, u in zip(cfd_r, cfd_U):
    ub = interpolate(r, bench_r, bench_U)
    ae = abs(u - ub)
    re = ae / ub * 100 if ub > 1e-12 else 0
    sum_rel += re
    max_err = max(max_err, ae)
    print(f"{r:9.4f}  {u:11.8f}  {ub:13.10f}  {ae:10.2e}  {re:9.4f}")

mean_rel = sum_rel / len(cfd_r)
cfd_maxU = max(cfd_U)
cfd_maxR = cfd_r[cfd_U.index(cfd_maxU)]

print(f"\n--- Summary ---")
print(f"Mean rel error:  {mean_rel:.4f} %")
print(f"Max abs error:   {max_err:.3e} m/s")
print(f"Benchmark Umag:  {bench_maxU:.6f} m/s @ r={bench_maxR:.4f} mm")
print(f"CFD Umag:        {cfd_maxU:.8f} m/s @ r={cfd_maxR:.4f} mm")

PASS = 1.0  # %
if mean_rel < PASS:
    print(f"\n*** VALIDATION PASSED (mean rel {mean_rel:.4f}% < {PASS}%) ***")
    sys.exit(0)
else:
    print(f"\n*** VALIDATION FAILED (mean rel {mean_rel:.4f}% >= {PASS}%) ***")
    sys.exit(1)
