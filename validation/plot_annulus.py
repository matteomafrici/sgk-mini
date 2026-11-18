#!/usr/bin/env python3
"""Generate validation figures: CFD vs analytical (annular Poiseuille flow).

Writes PNGs to validation/figures/. Run it via validation/run_annulus.sh, or
directly after a solver run.

Figures:
  01_velocity_profile.png  radial profiles at three axial stations, CFD vs analytical
  02_fields_velocity.png   meridional maps (x-r): CFD, analytical, difference
  03_pressure.png          reconstructed pressure drop, CFD vs analytical
  04_metrics_summary.png   value comparison table (CFD vs analytical, error, criterion)

matplotlib is a plotting-only dependency of this script; numpy is already
required by the validation itself.
"""

import argparse
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


def load(case_dir, bench_path, log_path, flux_path):
    meta, bench = va.check_inputs(case_dir, bench_path, verbose=False)
    time_name = va.latest_time_dir(case_dir)
    if time_name is None:
        raise SystemExit(f"No solver time directories in {case_dir}")

    x, r_face, ux, p_kin = va.extract_profile(case_dir, time_name, meta)

    dpL = bench["PressureGradientPaPerM"]
    mu = bench["DynamicViscosityPaS"]
    rho = bench["DensityKgPerM3"]
    ux_ana = np.array([va.U_analytical(rr, meta["Ri"], meta["Ro"], dpL, mu) for rr in r_face])
    ux_ana_field = np.tile(ux_ana, (len(x), 1))

    report = va.build_report(case_dir, bench_path, log_path, flux_path)

    return {
        "meta": meta,
        "bench": bench,
        "time_name": time_name,
        "x": x,
        "r": r_face,
        "ux": ux,
        "ux_ana": ux_ana_field,
        "p": p_kin * rho,
        "report": report,
    }


def fig_velocity_profile(d, path):
    x, r, ux, ux_ana = d["x"], d["r"], d["ux"], d["ux_ana"]
    Umax_b = d["report"]["umax_bench"]
    r_mm = r * 1e3

    stations = [
        (int(np.argmin(np.abs(x - 0.1 * (x[-1] - x[0]) - x[0]))), "near inlet"),
        (int(np.argmin(np.abs(x - 0.5 * (x[0] + x[-1])))), "mid-length"),
        (int(np.argmin(np.abs(x - 0.9 * (x[-1] - x[0]) - x[0]))), "near outlet"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, (i, label) in zip(axes, stations):
        ax.plot(r_mm, ux_ana[i], "-k", lw=2, label="analytical")
        ax.plot(r_mm, ux[i], "o", ms=4, color="#d62728", label="CFD")
        err = np.abs(ux[i] - ux_ana[i]) / Umax_b * 100.0
        ax.set_title(f"{label}  (x={x[i] * 1e3:.1f} mm)")
        ax.set_xlabel("face radius r (mm)")
        ax.grid(True, alpha=0.3)
        ax.text(
            0.03,
            0.95,
            f"mean |err|/Umax = {err.mean():.3f} %\nmax  |err|/Umax = {err.max():.3f} %",
            transform=ax.transAxes,
            va="top",
            fontsize=9,
            bbox=dict(facecolor="lightyellow", edgecolor="0.7", boxstyle="round,pad=0.35"),
        )
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
    Umax_b = d["report"]["umax_bench"]

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
    axes[2].set_title(f"difference (CFD − analytic)\nmax |ΔUx|/Umax = {lim / Umax_b * 100:.2f} %")
    fig.colorbar(im2, ax=axes[2])

    for ax in axes:
        ax.set_xlabel("axial position x (mm)")
        ax.grid(False)
    axes[0].set_ylabel("face radius r (mm)")

    fig.suptitle("Axial velocity field on the meridional (x-r) plane", y=1.03)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def fig_pressure(d, path):
    x = d["x"]
    # The pressure is axisymmetric: average the radial profile at each station.
    p = d["p"].mean(axis=1)
    dpL = d["report"]["dpL_bench"]
    dpL_cfd = d["report"]["dpL_cfd"]
    x_mm = x * 1e3

    # Analytical pressure, anchored at the inlet (p=0). The CFD pressure is
    # periodic: the gradient lives in the meanVelocityForce source term, so the
    # linear part is reconstructed with the solver's own gradient.
    p_ana = -dpL * (x - x[0])
    p_cfd = (p - p[0]) - dpL_cfd * (x - x[0])

    fig, (ax, axr) = plt.subplots(1, 2, figsize=(13, 4.8),
                                  gridspec_kw={"width_ratios": [3, 2]})

    ax.plot(x_mm, p_ana, "-k", lw=2, label=f"analytical  (dpL = {dpL:.3f} Pa/m)")
    ax.plot(x_mm, p_cfd, "--", color="#d62728", lw=2,
            label=f"CFD reconstructed  (dpL = {dpL_cfd:.3f} Pa/m)")
    ax.set_xlabel("axial position x (mm)")
    ax.set_ylabel("pressure relative to inlet (Pa)")
    ax.set_title(f"Pressure drop along the annulus  (error {abs(dpL_cfd - dpL) / dpL * 100:.3f} %)")
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
    report = d["report"]
    bench = d["bench"]

    rows = [
        ("peak velocity Umax", f"{report['umax_cfd']:.8f} m/s",
         f"{report['umax_bench']:.8f} m/s", report["umax_err_pct"], va.TOL["umax_pct"]),
        ("pressure gradient dpL", f"{report['dpL_cfd']:.6f} Pa/m",
         f"{report['dpL_bench']:.6f} Pa/m", report["dpL_err_pct"], va.TOL["dpL_pct"]),
        ("flow rate Q", f"{report['Q_full_native'] * 1e6:.6f} mL/s",
         f"{report['Q_bench'] * 1e6:.6f} mL/s", report["Q_err_pct"], va.TOL["q_pct"]),
        ("mean profile |err|/Umax", f"{report['profile']['mean_pct']:.3f} %", "0 %",
         report["profile"]["mean_pct"], va.TOL["mean_pct"]),
        ("max  profile |err|/Umax", f"{report['profile']['max_pct']:.3f} %", "0 %",
         report["profile"]["max_pct"], va.TOL["max_pct"]),
        ("rms  profile |err|/Umax", f"{report['profile']['rms_pct']:.3f} %", "0 %",
         report["profile"]["rms_pct"], None),
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

    for k, (name, cfd, ana, err, tol) in enumerate(rows):
        y = y_head - 0.13 * (k + 1)
        status = "—" if tol is None else ("PASS" if err <= tol else "FAIL")
        color = {"PASS": "#2e7d32", "FAIL": "#c62828", "—": "0.4"}[status]
        ax.text(colx[0], y, name, fontsize=10, va="center")
        ax.text(colx[1], y, cfd, fontsize=10, family="monospace", va="center")
        ax.text(colx[2], y, ana, fontsize=10, family="monospace", va="center")
        ax.text(colx[3], y, f"{err:.4f}", fontsize=10, family="monospace", va="center")
        ax.text(colx[4], y, "—" if tol is None else f"< {tol:g} %", fontsize=10, va="center")
        ax.text(colx[5], y, status, fontsize=10, fontweight="bold",
                color=color, ha="center", va="center")

    meta = d["meta"]
    fig.text(
        0.5, 0.965,
        "Validation values — annular Poiseuille flow\n"
        f"Ri={meta['Ri'] * 1e3:.4f} mm, Ro={meta['Ro'] * 1e3:.4f} mm, "
        f"Re={bench['ReynoldsNumber']:.2f}, "
        f"{meta['nX']}x{meta['nR1'] + meta['nR2']}x{meta['nAng']} cells, "
        f"{meta['totalAngleDeg']:.2f} deg wedge, {d['time_name']} iterations",
        ha="center", va="top", fontsize=11)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=va.DEFAULT_CASE)
    parser.add_argument("--benchmark", default=va.DEFAULT_BENCH)
    parser.add_argument("--log", default=None)
    parser.add_argument("--flux-log", default=None)
    parser.add_argument("--report", default=None,
                        help="unused; kept for run_annulus.sh compatibility")
    args = parser.parse_args()

    case_dir = os.path.abspath(args.case)
    bench_path = os.path.abspath(args.benchmark)
    log_path = args.log or os.path.join(case_dir, "log.simpleFoam")
    flux_path = args.flux_log or os.path.join(case_dir, "log.flux")

    os.makedirs(FIGDIR, exist_ok=True)
    d = load(case_dir, bench_path, log_path, flux_path)
    fig_velocity_profile(d, os.path.join(FIGDIR, "01_velocity_profile.png"))
    fig_fields_velocity(d, os.path.join(FIGDIR, "02_fields_velocity.png"))
    fig_pressure(d, os.path.join(FIGDIR, "03_pressure.png"))
    fig_metrics(d, os.path.join(FIGDIR, "04_metrics_summary.png"))
    print(f"Figures written to {FIGDIR}")


if __name__ == "__main__":
    main()
