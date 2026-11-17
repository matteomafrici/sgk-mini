#!/usr/bin/env python3
"""Generate validation figures: CFD vs analytical (annular Poiseuille flow).

Writes PNGs to validation/figures/ so that a reader who does not clone the
repository can see the results from the top-level README.

Figures:
  01_velocity_profile.png  radial profiles at three axial stations, CFD vs analytical
  02_fields_velocity.png   meridional maps (x-r): CFD, analytical, difference
  03_pressure.png          reconstructed pressure drop, CFD vs analytical
  04_metrics_summary.png   value comparison table (CFD vs analytical, error, criterion)
"""

import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_annulus as va  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")

# acceptance thresholds (same intent as validate_annulus.py)
TOL = {"umax": 1.0, "dpl": 5.0, "q": 2.0, "mean": 5.0}


def load():
    with open(va.BENCH) as f:
        bench = json.load(f)
    Ri = bench["InnerRadiusMm"] / 1000.0
    Ro = bench["OuterRadiusMm"] / 1000.0
    dpL = bench["PressureGradientPaPerM"]
    mu = bench["DynamicViscosityPaS"]
    rho = bench["DensityKgPerM3"]
    Umax_b = bench["MaxVelocityMPerS"]
    Q_b = bench["VolumetricFlowRateM3PerS"]

    time_name = va.latest_time_dir(va.CASE)
    x, r, ux, p = va.extract_profile(va.CASE, time_name, rho)
    sidx = np.argsort(r)
    r_s, ux_s = r[sidx], ux[:, sidx]

    dpL_cfd = va.solver_dpL_from_log(va.LOG, rho)

    ux_ana = np.array([va.U_analytical(rr, Ri, Ro, dpL, mu) for rr in r_s])
    ux_ana_field = np.tile(ux_ana, (len(x), 1))

    Q_prof = va.Q_from_ux(ux_s, r_s)
    i_mid = int(np.argmin(np.abs(x - 0.025)))
    return dict(
        bench=bench, Ri=Ri, Ro=Ro, dpL=dpL, mu=mu, rho=rho,
        Umax_b=Umax_b, Q_b=Q_b, time_name=time_name,
        x=x, r=r_s, ux=ux_s, ux_ana=ux_ana_field, p=p,
        dpL_cfd=dpL_cfd, Q_prof=Q_prof, i_mid=i_mid,
    )


def fig_velocity_profile(d, path):
    x, r, ux, ux_ana = d["x"], d["r"], d["ux"], d["ux_ana"]
    Umax_b = d["Umax_b"]
    r_mm = r * 1e3

    stations = [
        (int(np.argmin(np.abs(x - 0.005))), "near inlet"),
        (d["i_mid"], "mid-length"),
        (int(np.argmin(np.abs(x - 0.045))), "near outlet"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, (i, lbl) in zip(axes, stations):
        ax.plot(r_mm, ux_ana[i], "-k", lw=2, label="analytical")
        ax.plot(r_mm, ux[i], "o", ms=4, color="#d62728", label="CFD")
        err = np.abs(ux[i] - ux_ana[i]) / Umax_b * 100.0
        ax.set_title(f"{lbl}  (x={x[i]*1e3:.1f} mm)")
        ax.set_xlabel("radius r (mm)")
        ax.grid(True, alpha=0.3)
        ax.text(0.03, 0.95,
                f"mean |err|/Umax = {err.mean():.3f} %\nmax  |err|/Umax = {err.max():.3f} %",
                transform=ax.transAxes, va="top", fontsize=9,
                bbox=dict(facecolor="lightyellow", edgecolor="0.7", boxstyle="round,pad=0.35"))
    axes[0].set_ylabel("axial velocity Ux (m/s)")
    axes[0].legend(loc="lower center")
    fig.suptitle("Annular Poiseuille flow — radial velocity profile: CFD vs analytical", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def fig_fields_velocity(d, path):
    x_mm = d["x"] * 1e3
    r_mm = d["r"] * 1e3
    ux, ux_ana = d["ux"], d["ux_ana"]
    diff = ux - ux_ana
    Umax_b = d["Umax_b"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.4))
    vmax = max(ux.max(), ux_ana.max())

    im0 = axes[0].pcolormesh(x_mm, r_mm, ux.T, shading="auto",
                             cmap="viridis", vmin=0, vmax=vmax)
    axes[0].set_title("CFD  Ux (m/s)")
    fig.colorbar(im0, ax=axes[0])

    im1 = axes[1].pcolormesh(x_mm, r_mm, ux_ana.T, shading="auto",
                             cmap="viridis", vmin=0, vmax=vmax)
    axes[1].set_title("analytical  Ux (m/s)")
    fig.colorbar(im1, ax=axes[1])

    lim = np.abs(diff).max() or 1e-9
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)
    im2 = axes[2].pcolormesh(x_mm, r_mm, diff.T, shading="auto",
                             cmap="coolwarm", norm=norm)
    axes[2].set_title(f"difference (CFD − analytic)\nmax |ΔUx|/Umax = {lim/Umax_b*100:.2f} %")
    fig.colorbar(im2, ax=axes[2])

    for ax in axes:
        ax.set_xlabel("axial position x (mm)")
        ax.grid(False)
    axes[0].set_ylabel("radius r (mm)")

    fig.suptitle("Axial velocity field on the meridional (x-r) plane", y=1.03)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def fig_pressure(d, path):
    x = d["x"]
    p = d["p"]
    dpL, dpL_cfd = d["dpL"], d["dpL_cfd"]
    x_mm = x * 1e3

    # Analytical pressure, anchored at the inlet (p=0).
    p_ana = -dpL * (x - x[0])
    # Reconstructed physical pressure from the CFD: the raw p is periodic
    # (meanVelocityForce carries the gradient in the source term), so the
    # linear part is rebuilt with the solver's own gradient.
    p_cfd = (p - p[0]) - dpL_cfd * (x - x[0])

    fig, (ax, axr) = plt.subplots(1, 2, figsize=(13, 4.8),
                                  gridspec_kw={"width_ratios": [3, 2]})

    ax.plot(x_mm, p_ana, "-k", lw=2, label=f"analytical  (dpL = {dpL:.3f} Pa/m)")
    ax.plot(x_mm, p_cfd, "--", color="#d62728", lw=2,
            label=f"CFD reconstructed  (dpL = {dpL_cfd:.3f} Pa/m)")
    ax.set_xlabel("axial position x (mm)")
    ax.set_ylabel("pressure relative to inlet (Pa)")
    ax.set_title(f"Pressure drop along the annulus  (error {abs(dpL_cfd-dpL)/dpL*100:.3f} %)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    axr.plot(x_mm, p, "o-", ms=2, color="#1f77b4")
    axr.set_xlabel("axial position x (mm)")
    axr.set_ylabel("raw CFD p (Pa)")
    axr.set_title("Raw CFD pressure is periodic\n(gradient lives in the source term)")
    axr.grid(True, alpha=0.3)
    axr.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def fig_metrics(d, path):
    x, ux, ux_ana = d["x"], d["ux"], d["ux_ana"]
    Umax_b, Q_b, dpL, dpL_cfd = d["Umax_b"], d["Q_b"], d["dpL"], d["dpL_cfd"]
    err = np.abs(ux - ux_ana) / Umax_b * 100.0
    mean_e, max_e, rms_e = err.mean(), err.max(), np.sqrt((err**2).mean())
    umax_cfd = ux[d["i_mid"]].max()
    umax_err = abs(umax_cfd - Umax_b) / Umax_b * 100.0
    dpl_err = abs(dpL_cfd - dpL) / dpL * 100.0
    Q_cfd = d["Q_prof"][-20:].mean()
    Q_err = abs(Q_cfd - Q_b) / Q_b * 100.0

    rows = [
        ("peak velocity Umax", f"{umax_cfd:.8f} m/s", f"{Umax_b:.8f} m/s", umax_err, TOL["umax"]),
        ("pressure gradient dpL", f"{dpL_cfd:.6f} Pa/m", f"{dpL:.6f} Pa/m", dpl_err, TOL["dpl"]),
        ("flow rate Q", f"{Q_cfd*1e6:.6f} mL/s", f"{Q_b*1e6:.6f} mL/s", Q_err, TOL["q"]),
        ("mean profile |err|/Umax", f"{mean_e:.3f} %", "0 %", mean_e, TOL["mean"]),
        ("max  profile |err|/Umax", f"{max_e:.3f} %", "0 %", max_e, None),
        ("rms  profile |err|/Umax", f"{rms_e:.3f} %", "0 %", rms_e, None),
    ]

    fig = plt.figure(figsize=(12.5, 4.6))
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    header = ["metric", "CFD", "analytical", "error [%]", "criterion", "status"]
    colx = [0.03, 0.30, 0.49, 0.66, 0.79, 0.93]
    y_head = 0.86

    for cx, h in zip(colx, header):
        ax.text(cx, y_head, h, fontsize=11, fontweight="bold",
                ha="center" if cx >= 0.9 else "left")
    ax.plot([0.02, 0.98], [y_head - 0.055, y_head - 0.055], color="0.5", lw=1)

    for k, (name, cfd, ana, e, tol) in enumerate(rows):
        y = y_head - 0.13 * (k + 1)
        status = "—" if tol is None else ("PASS" if e <= tol else "FAIL")
        color = {"PASS": "#2e7d32", "FAIL": "#c62828", "—": "0.4"}[status]
        ax.text(colx[0], y, name, fontsize=10, va="center")
        ax.text(colx[1], y, cfd, fontsize=10, family="monospace", va="center")
        ax.text(colx[2], y, ana, fontsize=10, family="monospace", va="center")
        ax.text(colx[3], y, f"{e:.4f}", fontsize=10, family="monospace", va="center")
        ax.text(colx[4], y, "—" if tol is None else f"< {tol:g} %", fontsize=10, va="center")
        ax.text(colx[5], y, status, fontsize=10, fontweight="bold",
                color=color, ha="center", va="center")

    bench = d["bench"]
    fig.text(
        0.5, 0.965,
        "Validation values — annular Poiseuille flow\n"
        f"Ri={d['Ri']*1e3:.4f} mm, Ro={d['Ro']*1e3:.4f} mm, "
        f"Re={bench['ReynoldsNumber']:.2f}, 80x100x3 cells, cyclic, {d['time_name']} iterations",
        ha="center", va="top", fontsize=11)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    os.makedirs(FIGDIR, exist_ok=True)
    d = load()
    fig_velocity_profile(d, os.path.join(FIGDIR, "01_velocity_profile.png"))
    fig_fields_velocity(d, os.path.join(FIGDIR, "02_fields_velocity.png"))
    fig_pressure(d, os.path.join(FIGDIR, "03_pressure.png"))
    fig_metrics(d, os.path.join(FIGDIR, "04_metrics_summary.png"))
    print(f"Figures written to {FIGDIR}")


if __name__ == "__main__":
    main()
