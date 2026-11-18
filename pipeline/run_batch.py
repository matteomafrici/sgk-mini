#!/usr/bin/env python3
"""Run a frozen annulus manifest and publish one result per physical point."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path

from annulus_case import DATASET_ROOT, Request, REPO, admissibility, run_case, sha256, write_json
from run_pilot import build


def read_json(path):
    with path.open() as stream:
        return json.load(stream)


def verify_record(path, request):
    record = read_json(path)
    if record["request"] != request.as_dict():
        raise ValueError(f"{path}: request does not match the manifest")
    for name, expected in record["artifacts"].items():
        if sha256(path.parent / name) != expected:
            raise ValueError(f"{path}: invalid artifact {name}")
    return record


def solve_point(point, root, voxel_trials):
    attempts = []
    for voxel in voxel_trials:
        request = Request.from_dict(point | {"voxel_size_mm": voxel})
        paths = sorted(
            (root / request.case_id / "attempts").glob("*/dataset-record.json"),
            key=lambda path: (path.stat().st_mtime_ns, path),
        )
        if not paths:
            run_case(request, str(root), require_geometry=True)
            paths = list((root / request.case_id / "attempts").glob("*/dataset-record.json"))
            if len(paths) != 1:
                raise ValueError(f"{request.case_id}: expected a single new attempt")
        record = verify_record(paths[-1], request)
        attempts.extend(str(path.relative_to(root)) for path in paths)
        geometry = record.get("geometry")
        reference = record.get("reference")
        if geometry is None or all(check["passed"] for check in geometry["checks"]):
            break
        if reference and reference["solver_exit_code"] is not None:
            raise ValueError(f"{request.case_id}: a rejected geometry reached the solver")

    return {
        "physical_case_id": point["case_id"],
        "split": point["split"],
        "radius_ratio": point["radius_ratio"],
        "status": record["status"],
        "failure_reason": record["failure_reason"],
        "selected_case_id": request.case_id if record["status"] == "ok" else None,
        "voxel_size_mm": request.voxel_size_mm,
        "record": str(paths[-1].relative_to(root)),
        "attempts": attempts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(REPO) / "pipeline/batch-cases-v1.json")
    parser.add_argument("--root", type=Path, default=Path(DATASET_ROOT) / "annulus-v1")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")

    manifest = read_json(args.manifest)
    points = manifest["cases"]
    voxel_trials = manifest["voxel_trials_mm"]
    if not voxel_trials or sorted(set(voxel_trials), reverse=True) != voxel_trials:
        parser.error("voxel sizes must be nonempty, unique and decreasing")
    ids = [Request.from_dict(point).case_id for point in points]
    if ids != [point["case_id"] for point in points] or len(set(ids)) != len(ids):
        parser.error("manifest case identities must be unique and match their parameters")
    if any(admissibility(Request.from_dict(point)) for point in points):
        parser.error("manifest contains inadmissible physical cases")

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen = root / "manifest.json"
        if frozen.exists() and read_json(frozen) != manifest:
            parser.error("dataset root is already bound to a different manifest")
        write_json(str(frozen), manifest)
        build()

        by_id = {
            point["case_id"]: {
                "physical_case_id": point["case_id"], "split": point["split"],
                "radius_ratio": point["radius_ratio"], "status": "pending",
            }
            for point in points
        }

        def publish():
            write_json(str(root / "index.json"), {
                "schema": "sgk-mini.batch-index.v1",
                "batch_id": manifest["batch_id"],
                "manifest_sha256": sha256(frozen),
                "cases": list(by_id.values()),
            })

        publish()
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(solve_point, p, root, voxel_trials): p for p in points}
            for done, future in enumerate(as_completed(futures), 1):
                point = futures[future]
                case_id = point["case_id"]
                try:
                    by_id[case_id] = future.result()
                except Exception as error:
                    by_id[case_id].update(status="failed", failure_reason=str(error))
                publish()
                entry = by_id[case_id]
                print(f"[{done}/{len(points)}] {case_id} {entry['split']}: "
                      f"{entry['status']} {entry.get('failure_reason') or ''}", flush=True)

    return int(any(row["status"] != "ok" for row in by_id.values()))


if __name__ == "__main__":
    raise SystemExit(main())
