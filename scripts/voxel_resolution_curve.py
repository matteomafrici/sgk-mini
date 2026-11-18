#!/usr/bin/env python3
"""Voxel resolution curve for sgk-mini.

Runs the geometry stage at several voxel sizes and records what changes:
wall time, peak memory, VDB size, and the reconstructed volume and radii
against the exact values of the nominal part.

The point is convergence: below some voxel size the measured volume stops
changing, and above it the geometry is being misrepresented.

Each sweep point runs in its own temporary output directory, so the ordinary
default artifacts in `output/` are never replaced by the last resolution of the
sweep.

Usage:
  scripts/voxel_resolution_curve.py
  scripts/voxel_resolution_curve.py --voxels 0.3 0.2 0.15 0.1 --write

With --write, only the generated table inside `validation/voxel-resolution-curve.md`
is replaced. The handwritten interpretation is left untouched.
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL = os.path.join(REPO, "src", "SGK.Geometry", "bin", "Debug", "net9.0", "SGK.Geometry.dll")
DOC = os.path.join(REPO, "validation", "voxel-resolution-curve.md")

BEGIN = "<!-- BEGIN GENERATED TABLE -->"
END = "<!-- END GENERATED TABLE -->"


def peak_rss_mb(proc, interval_s=0.02):
    """Peak resident set size of a process, polled from /proc (Linux only).

    Stops when the process exits. A zombie keeps its /proc entry, so the exit
    condition is the process state, not the file's existence.
    """
    status = f"/proc/{proc.pid}/status"
    peak_kb = 0

    while True:
        try:
            with open(status) as f:
                state_zombie = False
                for line in f:
                    if line.startswith("VmHWM:"):
                        peak_kb = max(peak_kb, int(line.split()[1]))
                    elif line.startswith("State:") and "Z" in line.split()[1]:
                        state_zombie = True
        except (FileNotFoundError, ProcessLookupError):
            return peak_kb / 1024.0

        if state_zombie or proc.poll() is not None:
            return peak_kb / 1024.0

        time.sleep(interval_s)


def run_case(voxel_mm, outer_mm, inner_mm, length_mm):
    case_id = f"sweep-voxel-{voxel_mm:g}"
    work_dir = tempfile.mkdtemp(prefix=f"sgk-voxel-{voxel_mm:g}-")

    config = {
        "CaseId": case_id,
        "OuterRadiusMm": outer_mm,
        "InnerRadiusMm": inner_mm,
        "LengthMm": length_mm,
        "VoxelSizeMm": voxel_mm,
        "OutputDirectory": work_dir,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        cfg_path = f.name

    features_path = os.path.join(work_dir, f"{case_id}.features.json")
    physical_path = os.path.join(work_dir, f"{case_id}.physical-case.json")
    vdb_path = os.path.join(work_dir, f"{case_id}.vdb")

    started = time.monotonic()
    proc = subprocess.Popen(
        ["dotnet", DLL, "--auto-exit", "--config", cfg_path],
        cwd=os.path.dirname(DLL),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    rss_mb = peak_rss_mb(proc)
    _, stderr = proc.communicate()
    elapsed = time.monotonic() - started
    os.unlink(cfg_path)

    if proc.returncode != 0:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise SystemExit(f"run failed at voxel {voxel_mm} mm:\n{stderr.decode()}")

    with open(features_path) as f:
        features = json.load(f)
    with open(physical_path) as f:
        physical = json.load(f)

    row = {
        "voxel_mm": voxel_mm,
        "elapsed_s": elapsed,
        "rss_mb": rss_mb,
        "vdb_mb": os.path.getsize(vdb_path) / (1024.0 * 1024.0),
        "volume_mm3": features["VolumeMm3"],
        "outer_recon_mm": physical["OuterRadiusMm"],
        "inner_recon_mm": physical["InnerRadiusMm"],
        "length_recon_mm": physical["LengthMm"],
    }

    # The sweep measures the artifacts; it does not keep them. The dataset
    # directory is the only place where generated data is retained.
    shutil.rmtree(work_dir, ignore_errors=True)
    return row


def build_table(rows, exact_volume):
    header = (
        "| Voxel (mm) | Wall time (s) | Peak RSS (MB) | VDB (MB) | Volume (mm^3) | "
        "Volume error (%) | Ro reconstructed (mm) | Ri reconstructed (mm) |"
    )
    sep = "|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for r in rows:
        err = 100.0 * (r["volume_mm3"] - exact_volume) / exact_volume
        lines.append(
            f"| {r['voxel_mm']} | {r['elapsed_s']:.2f} | {r['rss_mb']:.0f} | "
            f"{r['vdb_mb']:.1f} | {r['volume_mm3']:.3f} | {err:+.4f} | "
            f"{r['outer_recon_mm']:.4f} and {r['inner_recon_mm']:.4f} |"
        )
    return "\n".join(lines)


def write_document(path, table, meta):
    with open(path) as f:
        text = f.read()

    if BEGIN not in text or END not in text:
        raise SystemExit(
            f"{path} has no generated-table markers. Add {BEGIN} and {END} "
            "around the table, then run with --write; refusing to overwrite prose."
        )

    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    generated = (
        f"{BEGIN}\n"
        f"Generated by `scripts/voxel_resolution_curve.py`. "
        f"Nominal part: Ro={meta['outer']} mm, Ri={meta['inner']} mm, "
        f"L={meta['length']} mm. Exact volume {meta['exact_volume']:.3f} mm^3.\n\n"
        f"{table}\n"
    )
    with open(path, "w") as f:
        f.write(head + generated + END + tail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voxels", nargs="+", type=float, default=[0.3, 0.2, 0.15, 0.1])
    parser.add_argument("--outer", type=float, default=10.0)
    parser.add_argument("--inner", type=float, default=8.0)
    parser.add_argument("--length", type=float, default=50.0)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    exact_volume = math.pi * (args.outer ** 2 - args.inner ** 2) * args.length

    print(f"nominal part: Ro={args.outer} Ri={args.inner} L={args.length} mm")
    print(f"exact volume {exact_volume:.3f} mm^3")
    print()

    rows = []
    for voxel in args.voxels:
        row = run_case(voxel, args.outer, args.inner, args.length)
        rows.append(row)
        print(
            f"voxel {voxel:>5} mm | {row['elapsed_s']:6.2f} s | "
            f"rss {row['rss_mb']:6.0f} MB | vdb {row['vdb_mb']:5.1f} MB | "
            f"V {row['volume_mm3']:9.3f} mm^3"
        )

    print()
    table = build_table(rows, exact_volume)
    print(table)

    if args.write:
        write_document(
            DOC,
            table,
            {"outer": args.outer, "inner": args.inner, "length": args.length,
             "exact_volume": exact_volume},
        )
        print(f"\nupdated generated table in: {DOC}")


if __name__ == "__main__":
    sys.exit(main())
