#!/usr/bin/env python3
"""Validate refined mesh (80x100x3 = 24000 cells, cyclic periodic)."""
import sys, os, json, math, re
import numpy as np

# Copy needed functions from validate_comprehensive
sys.path.insert(0, os.path.expanduser("~/work/sgk-mini/cases/annulus"))
mod_code = open(os.path.expanduser("~/work/sgk-mini/cases/annulus/validate_comprehensive.py")).read()
# Extract just function definitions (before if __name__)
mod_globals = {}
exec(mod_code.split("if __name__")[0], mod_globals)
read_field = mod_globals["read_field"]
extract_profile = mod_globals["extract_profile"]
Q_from_ux = mod_globals["Q_from_ux"]

def U_analytical(r, Ri, Ro, dpL, mu):
    return (dpL / (4.0 * mu)) * (
        Ro * Ro - r * r +
        (Ro * Ro - Ri * Ri) * math.log(r / Ro) / math.log(Ro / Ri)
    )

bench_path = os.path.expanduser("~/work/sgk-mini/output/hollow-cylinder.physical-case.json")
case_dir = os.path.expanduser("~/work/sgk-mini/cases/annulus_refined")

with open(bench_path) as f:
    bench = json.load(f)
Ri = bench["InnerRadiusMm"] / 1000
Ro = bench["OuterRadiusMm"] / 1000
dpL = bench["PressureGradientPaPerM"]
mu = bench["DynamicViscosityPaS"]
rho = bench["DensityKgPerM3"]
Umax_b = bench["MaxVelocityMPerS"]
Q_b = bench["VolumetricFlowRateM3PerS"]

nX, nR1, nR2 = 80, 50, 50
x, r, ux, p = extract_profile(case_dir, nX, nR1, nR2, rho=rho)

sidx = np.argsort(r)
r_s = r[sidx]
ux_s = ux[:, sidx]

Q_prof, areas = Q_from_ux(ux_s, r_s, nX, nR1, nR2)
i_mid = np.argmin(np.abs(x - 0.025))
ua_mid = np.array([U_analytical(rr, Ri, Ro, dpL, mu) for rr in r_s])
ux_mid = ux_s[i_mid, :]

abs_err = np.abs(ux_mid - ua_mid)
rel_err_pct = abs_err / Umax_b * 100

results = {
    "mean_rel_pct": float(np.mean(rel_err_pct)),
    "max_rel_pct": float(np.max(rel_err_pct)),
    "rms_rel_pct": float(np.sqrt(np.mean(rel_err_pct**2))),
    "cfd_umax": float(np.max(ux_mid)),
    "cfd_umax_r_mm": float(r_s[np.argmax(ux_mid)] * 1000),
    "umax_err_pct": float(abs(np.max(ux_mid) - Umax_b) / Umax_b * 100),
    "dpL_cfd": 0.026909861 * rho,  # from solver output
    "dpL_bench": dpL,
    "dpL_err_pct": float(abs(0.026909861 * rho - dpL) / dpL * 100),
    "Q_cfd_mls": float(np.mean(Q_prof[-20:]) * 1e6),
    "Q_bench_mls": float(Q_b * 1e6),
    "Q_err_pct": float(abs(np.mean(Q_prof[-20:]) - Q_b) / Q_b * 100),
}

# Print
print(f"{'Metric':<40s} {'Value':>12s}")
print(f"{'-'*40} {'-'*12}")
for k, v in results.items():
    print(f"  {k:<38s} {v:>12.6f}")

print(f"\n  Mean |err|/Umax:  {results['mean_rel_pct']:.4f}%")
print(f"  Max  |err|/Umax:  {results['max_rel_pct']:.4f}%")
print(f"  Umax error:       {results['umax_err_pct']:.4f}%")
print(f"  dpL error:        {results['dpL_err_pct']:.4f}%")
print(f"  Q error:          {results['Q_err_pct']:.4f}%")
