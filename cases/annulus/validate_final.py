#!/usr/bin/env python3
"""Validate CFD velocity profile against closed-form annular Poiseuille solution."""

import json, math, re, sys

CASE = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"

with open(f"{CASE}/../../output/hollow-cylinder.physical-case.json") as f:
    bench = json.load(f)

Ri = bench["InnerRadiusMm"] / 1000
Ro = bench["OuterRadiusMm"] / 1000
k = Ri / Ro
dpL = bench["PressureGradientPaPerM"]
mu = bench["DynamicViscosityPaS"]
Umax = bench["MaxVelocityMPerS"]

def U_analytical(r_m):
    """Annular Poiseuille profile: dpL = pressure gradient (Pa/m), mu = viscosity (Pa·s)."""
    xi = r_m / Ro
    return (dpL * Ro**2 / (4 * mu)) * (1 - xi**2 + (1 - k**2) * math.log(xi) / math.log(Ro/Ri))

# Verify against benchmark samples
print("Analytical formula vs benchmark samples:")
for s in bench["VelocityProfileSamples"]:
    r = s["RadiusMm"] / 1000
    ub = s["AxialVelocityMPerS"]
    uf = U_analytical(r)
    print(f"  r={s['RadiusMm']:.4f}mm  bench={ub:.8f}  formula={uf:.8f}")
print()

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
    if r < bench["InnerRadiusMm"] or r > bench["OuterRadiusMm"]:
        continue
    cfd_r.append(r / 1000)
    cfd_U.append(U[idx][0])

for j in range(nR2):
    idx = b1 + 1 * nR2 * nX + j * nX + 40
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2) * 1000
    if r < bench["InnerRadiusMm"] or r > bench["OuterRadiusMm"]:
        continue
    cfd_r.append(r / 1000)
    cfd_U.append(U[idx][0])

print(f"{'r (mm)':>9s}    {'U_CFD':>10s}    {'U_anal':>12s}    {'|err|':>9s}    {'|err|/Umax':>9s}")
print("-" * 67)

max_abs = 0.0
sum_abs = 0.0
sum_rel = 0.0

for r, u in zip(cfd_r, cfd_U):
    ua = U_analytical(r)
    ae = abs(u - ua)
    ar = ae / Umax * 100
    sum_abs += ae
    sum_rel += ar
    max_abs = max(max_abs, ae)
    print(f"{r*1000:9.4f}    {u:10.7f}    {ua:12.9f}    {ae:9.2e}    {ar:9.4f}")

n = len(cfd_r)
mean_abs = sum_abs / n
mean_rel = sum_rel / n
cfd_maxU = max(cfd_U)
cfd_maxR = cfd_r[cfd_U.index(cfd_maxU)] * 1000
anal_maxR = bench["MaxVelocityRadiusMm"]

print(f"\n--- Summary (n={n}) ---")
print(f"Mean |err|:          {mean_abs:.3e} m/s")
print(f"Mean |err|/Umax:     {mean_rel:.4f} %")
print(f"Max |err|:           {max_abs:.3e} m/s ({max_abs/Umax*100:.4f}% of Umax)")
print(f"Analytical Umax:     {Umax:.6f} m/s @ r={anal_maxR:.4f} mm")
print(f"CFD Umax:            {cfd_maxU:.8f} m/s @ r={cfd_maxR:.4f} mm")
print(f"CFD Umax error:      {abs(cfd_maxU-Umax):.3e} ({abs(cfd_maxU-Umax)/Umax*100:.4f}%)")

PASS = 1.0
if mean_rel < PASS:
    print(f"\n*** VALIDATION PASSED (mean|err|/Umax={mean_rel:.4f}% < {PASS}%) ***")
    sys.exit(0)
else:
    print(f"\n*** VALIDATION FAILED (mean|err|/Umax={mean_rel:.4f}% >= {PASS}%) ***")
    sys.exit(1)
