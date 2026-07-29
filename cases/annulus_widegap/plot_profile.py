#!/usr/bin/env python3
"""2D plot: CFD velocity profile vs analytical for widegap annular case."""

import json, math, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CASE = "/home/matteo-mafrici/work/sgk-mini/cases/annulus_widegap"
BENCH = "/home/matteo-mafrici/work/sgk-mini/output/hollow-cylinder-widegap.physical-case.json"

with open(BENCH) as f:
    bench = json.load(f)

Ri = bench["InnerRadiusMm"] / 1000
Ro = bench["OuterRadiusMm"] / 1000
k = Ri / Ro
dpL = bench["PressureGradientPaPerM"]
mu = bench["DynamicViscosityPaS"]
Umax = bench["MaxVelocityMPerS"]
Umean = bench["MeanVelocityMPerS"]

def U_analytical(r):
    xi = r / Ro
    return (dpL * Ro**2 / (4 * mu)) * (1 - xi**2 + (1 - k**2) * math.log(xi) / math.log(Ro/Ri))

def read_field(path):
    with open(path) as f: text = f.read()
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    n, body = int(m.group(1)), m.group(2)
    vals = [tuple(float(x) for x in t.strip().split()) for t in re.findall(r"\(([^)]+)\)", body)]
    assert len(vals) == n
    return vals

C = read_field(f"{CASE}/200/C")
U = read_field(f"{CASE}/200/U")

nX, nR1, nR2, nAng = 80, 25, 25, 3
b1 = nX * nR1 * nAng
cr, cU = [], []

for j in range(nR1):
    idx = 1 * nR1 * nX + j * nX + 40
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2)
    if r < Ri or r > Ro: continue
    cr.append(r * 1000)
    cU.append(U[idx][0])
for j in range(nR2):
    idx = b1 + 1 * nR2 * nX + j * nX + 40
    cx, cy, cz = C[idx]
    r = math.sqrt(cy**2 + cz**2)
    if r < Ri or r > Ro: continue
    cr.append(r * 1000)
    cU.append(U[idx][0])

analytical_r = [r_mm / 1000 for r_mm in cr]
analytical_U = [U_analytical(r) for r in cr]

max_abs = max(abs(u - U_analytical(r/1000)) for r, u in zip(cr, cU))
mean_abs = sum(abs(u - U_analytical(r/1000)) for r, u in zip(cr, cU)) / len(cr)
print(f"n={len(cr)}, mean|err|={mean_abs:.3e} m/s ({mean_abs/Umax*100:.2f}% of Umax)")
print(f"max|err|={max_abs:.3e} m/s ({max_abs/Umax*100:.2f}% of Umax)")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# --- Panel 1: Radial profile ---
ax1.plot(cr, analytical_U, "-k", linewidth=2, label="Analytical")
ax1.plot(cr, cU, "or", markersize=3, label="CFD (simpleFoam)")
ax1.set_xlabel("Radius r (mm)")
ax1.set_ylabel("Axial Velocity Ux (m/s)")
ax1.set_title("Radial Velocity Profile — Widegap Annulus")
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(Ri*1000 - 1, Ro*1000 + 1)

# Annotate key parameters
text = (f"Ri={Ri*1000:.2f} mm  Ro={Ro*1000:.1f} mm  κ={k:.3f}\n"
        f"Umax={Umax:.4f} m/s  Umean={Umean:.5f} m/s\n"
        f"Re={bench['ReynoldsNumber']:.1f}\n"
        f"Mesh: 80×50×3 = 12k cells")
ax1.text(0.97, 0.03, text, transform=ax1.transAxes, fontsize=9,
         verticalalignment="bottom", horizontalalignment="right",
         bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7))

# --- Panel 2: Absolute error ---
errors = [abs(u - U_analytical(r/1000)) for r, u in zip(cr, cU)]
ax2.semilogy(cr, errors, "ob", markersize=3)
ax2.axhline(y=0.01*Umax, color="gray", linestyle="--", alpha=0.5, label="1% of Umax")
ax2.axhline(y=0.05*Umax, color="gray", linestyle=":", alpha=0.5, label="5% of Umax")
ax2.set_xlabel("Radius r (mm)")
ax2.set_ylabel("|U_CFD − U_analytical| (m/s)")
ax2.set_title("Absolute Error")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.set_xlim(Ri*1000 - 1, Ro*1000 + 1)

plt.tight_layout()
plt.savefig(f"{CASE}/profile_widegap.png", dpi=150)
print(f"Saved: {CASE}/profile_widegap.png")
