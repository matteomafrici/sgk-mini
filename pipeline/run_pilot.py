#!/usr/bin/env python3
"""Run the annular pilot: geometry, reference CFD, record assembly and checks.

Stops after the requested number of cases. It never trains anything and never
generates the full dataset.

Usage:
  pipeline/run_pilot.py                  # all cases in pipeline/pilot-cases.json
  pipeline/run_pilot.py --only ann-XXXX  # one case, for a retry or a test
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annulus_case import (  # noqa: E402
    DATASET_ROOT,
    REPO,
    Request,
    index_entries,
    run_case,
)

REPORTS = os.path.join(REPO, "pipeline", "reports")


def build():
    result = subprocess.run(
        ["dotnet", "build", "src/SGK.Geometry/", "-c", "Debug"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        raise SystemExit("dotnet build failed")


def write_report(entries, design):
    os.makedirs(REPORTS, exist_ok=True)

    with open(os.path.join(REPORTS, "pilot-index.json"), "w") as f:
        json.dump(entries, f, indent=2)

    lines = [
        "# Annulus pilot — case table",
        "",
        f"Generated from the dataset records. Design: seed {design['seed']}, "
        f"pool {design['pool_size']}, {design['selected_count']} cases, minimum "
        f"normalized distance {design['minimum_normalized_distance']:.4f}.",
        "",
        "No surrogate is trained. \"Prediction\" in this table is the CFD "
        "reference (and the geometry stage that feeds it); the analytical "
        "solution is the reference. The flow, dpL and profile columns are the "
        "measured errors against it.",
        "",
        "| Case | Ro (mm) | gap (mm) | L (mm) | Q (m3/s) | Re | "
        "flow err (%) | dpL err (%) | profile mean/max (%) | status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for entry in entries:
        row = entry
        profile = "—"
        if row.get("profile_mean_pct") is not None:
            profile = f"{row['profile_mean_pct']:.4f} / {row['profile_max_pct']:.4f}"
        flow = "—" if row.get("flow_error_pct") is None else f"{row['flow_error_pct']:.4f}"
        dpl = "—" if row.get("dpL_error_pct") is None else f"{row['dpL_error_pct']:.4f}"
        lines.append(
            f"| {row['case_id']} | {row['outer_radius_mm']:.3f} | "
            f"{row['gap_mm']:.3f} | {row['length_mm']:.2f} | "
            f"{row['flow_rate_m3_s']:.3e} | {row['reynolds']:.1f} | "
            f"{flow} | {dpl} | {profile} | {row['status']} |"
        )

    lines += [
        "",
        "## Acceptance criteria",
        "",
        "Geometry: reconstructed radii and length within 10 um, volume error "
        "below 0.1 %, VDB round trip, requested and produced records agree.",
        "",
        "Reference: guarded inputs, Mesh OK, finite fields, convergence criteria "
        "met, conservation imbalance < 1e-6, full-circle flow error < 0.05 %, "
        "pressure-gradient error < 0.5 %, profile mean < 1 % and max < 2.5 % of "
        "Umax.",
        "",
        "## Failures",
        "",
    ]

    failed = [e for e in entries if e["status"] != "ok"]
    if not failed:
        lines.append("None. Every requested case produced a complete record.")
    else:
        for entry in failed:
            lines.append(f"- {entry['case_id']}: {entry['failure_reason']}")

    with open(os.path.join(REPORTS, "pilot-table.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=os.path.join(REPO, "pipeline", "pilot-cases.json"))
    parser.add_argument("--root", default=DATASET_ROOT)
    parser.add_argument("--only", default=None)
    args = parser.parse_args()

    with open(args.cases) as f:
        design = json.load(f)

    requests = [Request.from_dict(values) for values in design["cases"]]
    if args.only:
        requests = [request for request in requests if request.case_id == args.only]
        if not requests:
            raise SystemExit(f"case {args.only} is not in {args.cases}")

    build()
    os.makedirs(args.root, exist_ok=True)

    entries = []
    for i, request in enumerate(requests, 1):
        print(f"[{i}/{len(requests)}] {request.case_id}: "
              f"Ro={request.outer_radius_mm:.2f} mm, gap={request.gap_mm:.2f} mm, "
              f"L={request.length_mm:.1f} mm, Q={request.flow_rate_m3_s:.2e} m3/s",
              flush=True)
        record = run_case(request, args.root)
        print(f"    {record['status']}"
              + ("" if record["status"] == "ok" else f": {record['failure_reason']}"),
              flush=True)
        entries.append({
            "case_id": record["case_id"],
            "status": record["status"],
            "failure_reason": record.get("failure_reason"),
            "outer_radius_mm": request.outer_radius_mm,
            "gap_mm": request.gap_mm,
            "length_mm": request.length_mm,
            "flow_rate_m3_s": request.flow_rate_m3_s,
            "reynolds": request.reynolds,
            "flow_error_pct": (record.get("reference") or {}).get("report", {}).get("Q_err_pct"),
            "dpL_error_pct": (record.get("reference") or {}).get("report", {}).get("dpL_err_pct"),
            "profile_mean_pct": ((record.get("reference") or {}).get("report") or {}).get("profile", {}).get("mean_pct"),
            "profile_max_pct": ((record.get("reference") or {}).get("report") or {}).get("profile", {}).get("max_pct"),
        })

    # Merge with cases already on disk, so a single-case retry does not erase
    # the rest of the index.
    all_entries = index_entries(args.root)
    write_report(all_entries, design)

    print(f"\nindex: {os.path.join(args.root, 'index.json')}")
    print(f"table: {os.path.join(REPORTS, 'pilot-table.md')}")

    return 0 if all(entry["status"] == "ok" for entry in all_entries) else 1


if __name__ == "__main__":
    sys.exit(main())
