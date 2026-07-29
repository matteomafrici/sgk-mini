#!/usr/bin/env python3
"""Validate CFD profile against analytical annular solution."""
import json, math, re, sys

CASE = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"
with open(f"{CASE}/../../output/hollow-cylinder.physical-case.json") as f:
    bench = json.load(f)

samples = bench["VelocityProfileSamples"]
bench_r = [s["RadiusMm"] for s in samples]
bench_U = [s["AxialVelocityMPerS"] for s in samples]
Ri = bench["InnerRadiusMm"]
Ro = bench["OuterRadiusMm"]
Umax = bench["MaxVelocityMPerS"]
Rmax = bench["MaxVelocityRadiusMm"]

def read_field(path):
    with open(path) as f:
        text = f.read()
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    n, body = int(m.group(1)), m.group(2)
    vals = [tuple(float(x) for x in t.strip().split()) for t in re.findall(r"\(([^)]+)\)", body)]
    assert len(vals) == n
    return vals

C = read_field(f"{CASE}/200/C")
U = read_field(f"{CASE}/200/U")

nX, nR1, nR2, nAng = 80, 25, 25, 3
b1 = nX * nR1 * nAng
cfd_r, cfd_U = [], []

for j in range(nR1):
    idx = 1 * nR1 * nX + j * nX + 40
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2) * 1000
    if r < Ri or r > Ro:
        continue
    cfd_r.append(r)
    cfd_U.append(U[idx][0])

for j in range(nR2):
    idx = b1 + 1 * nR2 * nX + j * nX + 40
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2) * 1000
    if r < Ri or r > Ro:
        continue
    cfd_r.append(r)
    cfd_U.append(U[idx][0])

def interpolate(x, xd, yd):
    if x <= xd[0]: return yd[0]
    if x >= xd[-1]: return yd[-1]
    for i in range(len(xd)-1):
        if xd[i] <= x <= xd[i+1]:
            t = (x - xd[i]) / (xd[i+1] - xd[i])
            return yd[i] + t * (yd[i+1] - yd[i])
    return yd[-1]

print(f"{'r (mm)':>9s}    {'U_CFD':>10s}    {'U_bench':>12s}    {'|err|':>9s}    {'|err|/Umax':>9s}")
print("-" * 67)

max_abs_err = 0.0
sum_abs_err = 0.0
sum_abs_rel = 0.0

for r, u in zip(cfd_r, cfd_U):
    ub = interpolate(r, bench_r, bench_U)
    ae = abs(u - ub)
    ar = ae / Umax * 100
    sum_abs_err += ae
    sum_abs_rel += ar
    max_abs_err = max(max_abs_err, ae)
    print(f"{r:9.4f}    {u:10.7f}    {ub:12.9f}    {ae:9.2e}    {ar:9.4f}")

n = len(cfd_r)
mean_abs_err = sum_abs_err / n
mean_abs_rel = sum_abs_rel / n
cfd_maxU = max(cfd_U)
cfd_maxR_at = cfd_r[cfd_U.index(cfd_maxU)]

print(f"\n--- Summary (n={n} radial samples) ---")
print(f"Ri={Ri:.4f} mm, Ro={Ro:.4f} mm")
print(f"Mean |err|:          {mean_abs_err:.3e} m/s")
print(f"Mean |err|/Umax:     {mean_abs_rel:.4f} %")
print(f"Max |err|:           {max_abs_err:.3e} m/s ({max_abs_err/Umax*100:.4f}% of Umax)")
print(f"Benchmark Umax:      {Umax:.6f} m/s @ r={Rmax:.4f} mm")
print(f"CFD Umax:            {cfd_maxU:.8f} m/s @ r={cfd_maxR_at:.4f} mm")
print(f"CFD Umax error:      {abs(cfd_maxU-Umax):.3e} m/s ({abs(cfd_maxU-Umax)/Umax*100:.4f}%)")

PASS = 1.0
if mean_abs_rel < PASS:
    print(f"\n*** VALIDATION PASSED (mean|err|/Umax={mean_abs_rel:.4f}% < {PASS}%) ***")
    sys.exit(0)
else:
    print(f"\n*** VALIDATION FAILED (mean|err|/Umax={mean_abs_rel:.4f}% >= {PASS}%) ***")
    sys.exit(1)
