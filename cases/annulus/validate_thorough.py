#!/usr/bin/env python3
"""Comprehensive CFD validation for concentric annular Poiseuille flow.

Reads OpenFOAM fields (C, U, p), computes radial profiles, axial development,
pressure drop, and error metrics against the closed-form analytical solution.
"""

import json, math, re, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def read_field(path):
    with open(path) as f:
        text = f.read()
    is_vector = "class       volVectorField" in text
    if is_vector:
        m = re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    else:
        m = re.search(r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([\s\S]*?)\)\s*;", text)
    n, body = int(m.group(1)), m.group(2)
    if is_vector:
        vals = [tuple(float(x) for x in t.strip().split()) for t in re.findall(r"\(([^)]+)\)", body)]
    else:
        vals = [float(x) for x in body.strip().split()]
    assert len(vals) == n, f"Expected {n}, got {len(vals)}"
    return vals


def U_analytical(r, Ri, Ro, dpL, mu):
    """Closed-form annular Poiseuille profile.

    U(r) = (dpL / 4*mu) * [Ro^2 - r^2 + (Ro^2 - Ri^2) * ln(r/Ro) / ln(Ro/Ri)]

    Gives U=0 at r=Ri and r=Ro, Umax > 0 in between.
    """
    return (dpL / (4.0 * mu)) * (
        Ro * Ro - r * r +
        (Ro * Ro - Ri * Ri) * math.log(r / Ro) / math.log(Ro / Ri)
    )


def parse_struct(case_dir, nX, nR1, nR2, nAng, rho=1.0):
    """Read OpenFOAM fields and return structured arrays.

    OpenFOAM stores kinematic pressure (p/rho); multiply by rho for physical.
    """
    C = read_field(f"{case_dir}/200/C")
    U = read_field(f"{case_dir}/200/U")
    p_raw = read_field(f"{case_dir}/200/p")
    p = [v * rho for v in p_raw]

    b1 = nX * nR1 * nAng  # block1 total cells
    b2 = nX * nR2 * nAng  # block2 total cells

    def extract(k, j, block):
        if block == 1:
            idx = k * nR1 * nX + j * nX
        else:
            idx = b1 + k * nR2 * nX + j * nX
        x = np.array([C[idx + i][0] for i in range(nX)])
        y = np.array([C[idx + i][1] for i in range(nX)])
        z = np.array([C[idx + i][2] for i in range(nX)])
        r = np.sqrt(y * y + z * z)
        ux = np.array([U[idx + i][0] for i in range(nX)])
        pr = np.array([p[idx + i] for i in range(nX)])
        return x, y, z, r, ux, pr

    return C, U, p, extract


def radial_profile_at_i(extract, i, nX, nR1, nR2, nAng, Ri, Ro):
    """Extract radial profile at a given axial index i and k=1 (middle angular layer)."""
    k = 1
    r_vals, u_vals = [], []
    for j in range(nR1):
        x, y, z, r, ux, _ = extract(k, j, 1)
        rr = r[i]
        if Ri < rr < Ro:
            r_vals.append(rr)
            u_vals.append(ux[i])
    for j in range(nR2):
        x, y, z, r, ux, _ = extract(k, j, 2)
        rr = r[i]
        if Ri < rr < Ro:
            r_vals.append(rr)
            u_vals.append(ux[i])
    idx = np.argsort(r_vals)
    return np.array(r_vals)[idx], np.array(u_vals)[idx]


def axial_profile_at_j(extract, j, block, nX, Ri, Ro, dpL, mu):
    """Extract axial profile at a given j, block, k=1."""
    k = 1
    x, y, z, r, ux, pr = extract(k, j, block)
    rr = np.mean(r)
    ua = U_analytical(rr, Ri, Ro, dpL, mu)
    return x, ux, ua, pr, rr


def wall_shear_stress(extract, nX, nR1, nR2, nAng, Ri, Ro, mu):
    """Estimate wall shear stress from near-wall velocity gradient."""
    k = 1
    # Inner wall: block 1, j=0 (nearest to inner radius)
    x0, y0, z0, r0, ux0, _ = extract(k, 0, 1)
    x1, y1, z1, r1, ux1, _ = extract(k, 1, 1)
    dr_inner = np.mean(r1 - r0)
    tau_inner = mu * np.mean((ux1 - ux0) / dr_inner)  # du/dr at inner wall, positive

    # Outer wall: block 2, j = nR2-1 (nearest to outer radius)
    x2, y2, z2, r2, ux2, _ = extract(k, nR2 - 1, 2)
    x3, y3, z3, r3, ux3, _ = extract(k, nR2 - 2, 2)
    dr_outer = np.mean(r3 - r2)
    du_outer = np.mean(ux3 - ux2)
    tau_outer = -mu * du_outer / dr_outer  # du/dr at outer wall (negative slope → positive stress)

    return tau_inner, tau_outer


# ──────────────────────────────────────────────
# Validation runs
# ──────────────────────────────────────────────

def validate_case(case_dir, bench_path, label, save_path, nX=80, nR1=25, nR2=25, nAng=3):
    with open(bench_path) as f:
        bench = json.load(f)

    Ri = bench["InnerRadiusMm"] / 1000.0
    Ro = bench["OuterRadiusMm"] / 1000.0
    dpL = bench["PressureGradientPaPerM"]
    mu = bench["DynamicViscosityPaS"]
    rho = bench["DensityKgPerM3"]
    Umax_bench = bench["MaxVelocityMPerS"]
    Rmax_bench = bench["MaxVelocityRadiusMm"]

    C, U, p, extract = parse_struct(case_dir, nX, nR1, nR2, nAng, rho)
    b1 = nX * nR1 * nAng

    # ── Panel A: radial profiles at 3 axial stations ──
    i_stations = [16, 40, 64]
    labels_a = [f"x={i * 0.05 / 80 + 0.05/160:.4f} m" for i in i_stations]
    profiles_a = {}
    for i, lb in zip(i_stations, labels_a):
        rp, up = radial_profile_at_i(extract, i, nX, nR1, nR2, nAng, Ri, Ro)
        profiles_a[lb] = (rp, up)

    # Analytical profile for plotting (compute at many r points)
    r_fine = np.linspace(Ri * 1.0001, Ro * 0.9999, 500)
    u_fine = np.array([U_analytical(r, Ri, Ro, dpL, mu) for r in r_fine])

    # ── Panel B: axial development at 3 radial positions ──
    j_inner = 2
    j_center = 12
    j_outer = nR2 - 3

    x_inner, ux_inner, ua_inner, _, r_inner = axial_profile_at_j(extract, j_inner, 1, nX, Ri, Ro, dpL, mu)
    x_centr, ux_centr, ua_centr, _, r_centr = axial_profile_at_j(extract, j_center, 1, nX, Ri, Ro, dpL, mu)
    x_outer, ux_outer, ua_outer, _, r_outer = axial_profile_at_j(extract, j_outer, 2, nX, Ri, Ro, dpL, mu)

    # ── Panel C: pressure drop ──
    _, _, _, pr_centr, _ = axial_profile_at_j(extract, j_center, 1, nX, Ri, Ro, dpL, mu)

    # Linear fit: p(x) = p0 - dpL_fit * x
    coeffs = np.polyfit(x_centr, pr_centr, 1)
    dpL_cfd = -coeffs[0]
    p0_cfd = coeffs[1]
    # Analytical: outlet (x=0.05m) at p=0, so p(x) = dpL * (L - x)
    L = 0.05

    # ── Panel D: error profile at mid-length ──
    r_err, u_err = radial_profile_at_i(extract, 40, nX, nR1, nR2, nAng, Ri, Ro)
    ua_err = np.array([U_analytical(r, Ri, Ro, dpL, mu) for r in r_err])
    rel_err_pct = np.abs(u_err - ua_err) / Umax_bench * 100.0

    # ── Metrics ──
    mean_rel = np.mean(rel_err_pct)
    max_rel = np.max(rel_err_pct)
    cfd_umax = np.max(u_err)
    cfd_umax_r = r_err[np.argmax(u_err)]
    umax_err_pct = abs(cfd_umax - Umax_bench) / Umax_bench * 100.0
    dp_err_pct = abs(dpL_cfd - dpL) / dpL * 100.0

    tau_inner, tau_outer = wall_shear_stress(extract, nX, nR1, nR2, nAng, Ri, Ro, mu)

    # ── Build figure ──
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"{label}\n{case_dir}", fontsize=13, y=0.98)

    # Panel A
    ax = axes[0, 0]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for (lb, (rp, up)), c in zip(profiles_a.items(), colors):
        ax.plot(rp * 1000, up, "o", ms=4, c=c, label=f"CFD {lb}")
    ax.plot(r_fine * 1000, u_fine, "-k", lw=1.5, label="Analytical")
    ax.set_xlabel("r (mm)")
    ax.set_ylabel("Ux (m/s)")
    ax.set_title("A: Radial profiles at 3 axial stations")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel B
    ax = axes[0, 1]
    for xv, uv, ua, rr, lbl, mk in [
        (x_inner, ux_inner, ua_inner, r_inner, f"j={j_inner}, r≈{r_inner*1000:.3f}mm", "s"),
        (x_centr, ux_centr, ua_centr, r_centr, f"j={j_center}, r≈{r_centr*1000:.3f}mm", "o"),
        (x_outer, ux_outer, ua_outer, r_outer, f"j={j_outer}, r≈{r_outer*1000:.3f}mm", "^"),
    ]:
        ax.plot(xv * 1000, uv, mk + "-", ms=3, label=f"CFD {lbl}")
        ax.axhline(y=ua, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("Ux (m/s)")
    ax.set_title("B: Axial development at 3 radial positions")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Panel C
    ax = axes[1, 0]
    ax.plot(x_centr * 1000, pr_centr, "o-", ms=3, label=f"CFD p(x)")
    x_anal = np.linspace(0, L, 100)
    p_anal = dpL * (L - x_anal)
    ax.plot(x_anal * 1000, p_anal, "-k", lw=1.5, label=f"Analytical (dpL={dpL:.6f} Pa/m)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("p (Pa)")
    ax.set_title("C: Pressure drop along annulus")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel D
    ax = axes[1, 1]
    ax.semilogy(r_err * 1000, rel_err_pct, "o-", ms=4, c="crimson")
    ax.axhline(y=1.0, color="green", ls="--", lw=1, label="1%")
    ax.axhline(y=5.0, color="orange", ls="--", lw=1, label="5%")
    ax.axhline(y=10.0, color="red", ls="--", lw=1, label="10%")
    ax.set_xlabel("r (mm)")
    ax.set_ylabel("|error| / Umax (%)")
    ax.set_title("D: Relative error profile at mid-length (log y)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(save_path, dpi=150)
    plt.close(fig)

    # ── Print metrics ──
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  Case: {case_dir}")
    print(f"{'='*70}")
    print(f"  Geometry: Ri={Ri*1000:.4f} mm, Ro={Ro*1000:.4f} mm")
    print(f"  Fluid: mu={mu} Pa·s")
    print(f"  Benchmark dpL={dpL:.6f} Pa/m")
    print(f"  Benchmark Umax={Umax_bench:.8f} m/s @ r={Rmax_bench:.4f} mm")
    print()
    print(f"  Mid-length radial profile (n={len(r_err)}):")
    print(f"    Mean |err|/Umax:  {mean_rel:.4f} %")
    print(f"    Max  |err|/Umax:  {max_rel:.4f} %")
    print()
    print(f"  Peak velocity:")
    print(f"    CFD Umax:         {cfd_umax:.8f} m/s @ r={cfd_umax_r*1000:.4f} mm")
    print(f"    Umax error:       {umax_err_pct:.4f} %")
    print()
    print(f"  Pressure gradient (linear fit over x={x_centr[0]*1000:.2f}–{x_centr[-1]*1000:.2f} mm):")
    print(f"    CFD dp/dx:        {dpL_cfd:.6f} Pa/m")
    print(f"    Benchmark dpL:    {dpL:.6f} Pa/m")
    print(f"    Error:            {dp_err_pct:.4f} %")
    print()
    print(f"  Wall shear stress (from near-wall gradient):")
    print(f"    Inner wall:       {tau_inner:.8f} Pa")
    print(f"    Outer wall:       {tau_outer:.8f} Pa")
    print(f"    Benchmark inner:  {bench.get('InnerWallShearStressPa', 'N/A')} Pa")
    print(f"    Benchmark outer:  {bench.get('OuterWallShearStressPa', 'N/A')} Pa")
    print()

    return {
        "mean_rel_pct": mean_rel,
        "max_rel_pct": max_rel,
        "cfd_umax": cfd_umax,
        "bench_umax": Umax_bench,
        "umax_err_pct": umax_err_pct,
        "dpL_cfd": dpL_cfd,
        "dpL_bench": dpL,
        "dpL_err_pct": dp_err_pct,
        "tau_inner": tau_inner,
        "tau_outer": tau_outer,
        "bench_tau_inner": bench.get("InnerWallShearStressPa"),
        "bench_tau_outer": bench.get("OuterWallShearStressPa"),
    }


# ──────────────────────────────────────────────
# Main: run both cases
# ──────────────────────────────────────────────

if __name__ == "__main__":
    base = "/home/matteo-mafrici/work/sgk-mini"

    # Case 1: narrow annulus
    m1 = validate_case(
        case_dir=f"{base}/cases/annulus",
        bench_path=f"{base}/output/hollow-cylinder.physical-case.json",
        label="Annulus (narrow gap, Ri=8mm, Ro=10mm)",
        save_path=f"{base}/cases/annulus/validation_thorough.png",
    )

    # Case 2: wide gap
    m2 = validate_case(
        case_dir=f"{base}/cases/annulus_widegap",
        bench_path=f"{base}/output/hollow-cylinder-widegap.physical-case.json",
        label="Annulus (wide gap, Ri=8mm, Ro=30mm)",
        save_path=f"{base}/cases/annulus_widegap/validation_thorough.png",
    )

    # ── Summary comparison ──
    print(f"\n{'='*70}")
    print("  SUMMARY COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Metric':<40s} {'Narrow':>12s} {'Widegap':>12s}")
    print(f"  {'-'*40} {'-'*12} {'-'*12}")
    for key, label in [
        ("mean_rel_pct", "Mean |err|/Umax (%)"),
        ("max_rel_pct", "Max |err|/Umax (%)"),
        ("umax_err_pct", "Umax error (%)"),
        ("dpL_err_pct", "dpL error (%)"),
    ]:
        print(f"  {label:<40s} {m1[key]:>12.4f} {m2[key]:>12.4f}")
    print()

    # Check file sizes
    import os
    for path, label in [
        (f"{base}/cases/annulus/validation_thorough.png", "Narrow"),
        (f"{base}/cases/annulus_widegap/validation_thorough.png", "Widegap"),
    ]:
        sz = os.path.getsize(path)
        print(f"  Saved: {path} ({sz / 1024:.1f} KB)")
