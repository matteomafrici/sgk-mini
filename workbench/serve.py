#!/usr/bin/env python3
"""Serve the local SGK workbench. The HTTP surface only reads artifacts."""

import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "validation"))
from validate_annulus import U_analytical
sys.path.insert(0, str(REPO / "pipeline"))
from annulus_case import Request

STATIC = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
          "/app.js": ("app.js", "text/javascript")}
LOGS = {"reference": "log.reference", "geometry": "log.geometry",
        "solver": "openfoam/log.simpleFoam", "mesh": "openfoam/log.checkMesh"}
DEFAULT_DATASET = Path.home() / "data/datasets/sgk-mini/annulus-v1"
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\Z")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise FileNotFoundError("Artifact outside configured root")
    return path


def tail(path, limit=24000):
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - limit))
        body = stream.read(limit).decode("utf-8", errors="replace")
    return body.partition("\n")[2] if size > limit else body


def recent_git():
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(REPO), "log", "-8",
         "--format=%h%x09%cI%x09%s"],
        capture_output=True, text=True, check=False, timeout=3,
    )
    return [
        dict(zip(("commit", "time", "subject"), line.split("\t", 2)))
        for line in result.stdout.splitlines()
    ]


def commit_diff(commit_id):
    if not any(row["commit"] == commit_id for row in recent_git()):
        raise FileNotFoundError("Commit is outside displayed history")
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(REPO), "show", "--no-color",
         "--no-ext-diff", "--no-textconv", "--format=short", "--stat", "--patch", commit_id, "--"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=3,
    )
    if result.returncode:
        raise FileNotFoundError(commit_id)
    maximum = 32000
    return {"text": result.stdout[:maximum], "truncated": len(result.stdout) > maximum}


class Dataset:
    def __init__(self, root, runs):
        self.root = root
        self.runs = runs

    def sources(self):
        index_path = self.root / "index.json"
        data = load(index_path)
        arrays_path = self.root / "model-inputs-v1/index.json"
        arrays = load(arrays_path)["cases"] if arrays_path.exists() else []
        return data, {entry["case_id"]: entry for entry in arrays}

    def training_runs(self):
        if not self.runs.is_dir():
            return []
        runs = []
        for child in sorted(self.runs.iterdir()):
            if not ID.fullmatch(child.name):
                continue
            try:
                path = within(self.runs, child.name + "/run.json")
                if path.is_file():
                    run = load(path)
                    runs.append({key: run.get(key) for key in (
                        "model", "status", "started_at", "updated_at", "commit", "command", "split",
                    )} | {"id": child.name})
            except (ValueError, OSError):
                continue
        return sorted(runs, key=lambda row: row.get("updated_at") or "", reverse=True)

    def pending_attempts(self, case_id, manifest, recovery):
        point = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
        if point is None:
            return []
        sizes = manifest["voxel_trials_mm"] + recovery.get(case_id, {}).get("extra_voxel_trials_mm", [])
        paths = []
        for size in sizes:
            request = Request.from_dict(point | {"voxel_size_mm": size})
            for path in within(self.root, request.case_id + "/attempts").glob("*/case-request.json"):
                path = within(self.root, str(path.relative_to(self.root)))
                if load(path) == request.as_dict():
                    paths.append(path)
        return [
            str(path.with_name("dataset-record.json").relative_to(self.root))
            for path in sorted(paths, key=lambda path: path.stat().st_mtime_ns)
        ]

    def attempt_record(self, path):
        if path.is_file():
            return load(path)
        request = load(within(self.root, str(path.with_name("case-request.json").relative_to(self.root))))
        phase = "Geometry"
        for key, label in (("mesh", "Mesh"), ("solver", "Solver"), ("reference", "Validation")):
            output = within(self.root, str((path.parent / LOGS[key]).relative_to(self.root)))
            if output.is_file():
                phase = label
        return {"status": "pending", "request": request, "case_id": request["case_id"],
                "phase": phase, "failure_reason": None}

    def overview(self):
        index, arrays = self.sources()
        manifest = load(self.root / "manifest.json") if self.root.joinpath("manifest.json").exists() else None
        recovery = load(self.root / "recovery.json") if self.root.joinpath("recovery.json").exists() else {}
        cases = []
        for entry in index["cases"]:
            attempts = entry.get("attempts", [])
            if not entry.get("record") and manifest:
                attempts = self.pending_attempts(entry["physical_case_id"], manifest, recovery)
            path = entry.get("record") or (attempts[-1] if attempts else None)
            record = self.attempt_record(within(self.root, path)) if path else {}
            request = record.get("request", {})
            report = (record.get("reference") or {}).get("report") or {}
            cases.append({
                "id": entry["physical_case_id"], "split": entry["split"],
                "status": entry["status"], "prepared": entry["physical_case_id"] in arrays,
                "attempts": len(attempts), "voxel": request.get("voxel_size_mm"),
                "phase": record.get("phase"),
                "ratio": entry.get("radius_ratio"), "gap": request.get("gap_mm"),
                "ro": request.get("outer_radius_mm"), "re": request.get("reynolds"),
                "flow": report.get("Q_field_err_pct"), "gradient": report.get("dpL_err_pct"),
                "commit": (record.get("provenance") or {}).get("git_commit", ""),
            })
        commits = recent_git()
        return {"batch": index["batch_id"], "cases": cases, "commits": commits,
                "runs": self.training_runs(), "dataset_updated": (self.root / "index.json").stat().st_mtime,
                "grid": [192, 192, 16] if arrays else []}

    def case(self, case_id):
        index, arrays = self.sources()
        entry = next((row for row in index["cases"] if row["physical_case_id"] == case_id), None)
        if entry and not entry.get("record") and self.root.joinpath("manifest.json").exists():
            manifest = load(self.root / "manifest.json")
            recovery = load(self.root / "recovery.json") if self.root.joinpath("recovery.json").exists() else {}
            paths = self.pending_attempts(case_id, manifest, recovery)
            if paths:
                entry = entry | {"record": paths[-1], "attempts": paths}
        if not entry or not entry.get("record"):
            raise FileNotFoundError(case_id)
        path = within(self.root, entry["record"])
        return entry, path, self.attempt_record(path), arrays.get(case_id)

    def detail(self, case_id):
        entry, path, record, array = self.case(case_id)
        attempts = []
        for reference in entry["attempts"]:
            previous = self.attempt_record(within(self.root, reference))
            attempts.append({
                "id": previous["case_id"], "selected": reference == entry["record"],
                "status": previous["status"], "reason": previous.get("failure_reason"),
                "voxel": previous["request"]["voxel_size_mm"],
            })
        physical = (record.get("geometry") or {}).get("physical") or {}
        reference = record.get("reference") or {}
        report = reference.get("report") or {}
        meta = load(within(self.root, "model-inputs-v1/" + array["metadata"])) if array else {}
        return {
            "id": case_id, "split": entry["split"], "request": record["request"],
            "phase": record.get("phase"),
            "attempts": attempts, "checks": reference.get("checks", []),
            "physical": {key: physical.get(key) for key in (
                "InnerRadiusMm", "OuterRadiusMm", "LengthMm", "ReynoldsNumber",
                "PressureGradientPaPerM", "VolumetricFlowRateM3PerS"
            )},
            "report": {key: report.get(key) for key in (
                "dpL_cfd", "Q_full_field", "Q_field_err_pct", "dpL_err_pct",
                "iterations", "mesh", "profile", "stopping_reason"
            )},
            "artifact": str(path.relative_to(self.root)),
            "provenance": {key: (record.get("provenance") or {}).get(key) for key in (
                "timestamp_utc", "git_commit", "git_dirty", "openfoam_version", "dotnet_version"
            )},
            "meta": {key: meta.get(key) for key in (
                "query_rows", "surface_points", "grid_shape", "sample_sha256", "normalization")},
        }

    def log(self, case_id, attempt, kind):
        entry, _, _, _ = self.case(case_id)
        if not 0 <= attempt < len(entry["attempts"]) or kind not in LOGS:
            raise FileNotFoundError("Unknown attempt or log")
        path = within(self.root, str(Path(entry["attempts"][attempt]).parent / LOGS[kind]))
        return {"name": path.name, "text": tail(path) if path.exists() else None}

    def run_metrics(self, run_id):
        run = next((row for row in self.training_runs() if row["id"] == run_id), None)
        if run is None:
            raise FileNotFoundError(run_id)
        metrics = within(self.runs, run_id + "/metrics.jsonl")
        log = within(self.runs, run_id + "/run.log")
        samples = []
        if metrics.exists():
            for line in tail(metrics, 120000).splitlines()[-360:]:
                try:
                    row = json.loads(line)
                    if {"step", "train_loss", "validation_loss"} <= row.keys() and all(
                            math.isfinite(row[key]) for key in ("step", "train_loss", "validation_loss")):
                        samples.append({key: row[key] for key in ("step", "train_loss", "validation_loss")})
                except (ValueError, TypeError, AttributeError):
                    continue
        return {"run": run, "metrics": samples, "log": tail(log) if log.exists() else None}

    def route(self, path):
        if path == "/api/overview":
            return self.overview()
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "runs"]:
            return self.run_metrics(parts[2])
        if len(parts) == 3 and parts[:2] == ["api", "commits"]:
            return commit_diff(parts[2])
        if len(parts) < 3 or parts[:2] != ["api", "cases"]:
            raise FileNotFoundError(path)
        case_id = parts[2]
        if len(parts) == 3:
            return self.detail(case_id)
        if parts[3:] == ["view"]:
            _, _, record, array = self.case(case_id)
            if array is None:
                raise FileNotFoundError("No prepared geometry")
            path = within(self.root, "model-inputs-v1/" + array["arrays"])
            return view_data(path, path.stat().st_mtime_ns, record["case_id"],
                             json.dumps(record["geometry"]["physical"]),
                             json.dumps(record["reference"]["report"]["mesh"]))
        if len(parts) == 6 and parts[3] == "attempts" and parts[4].isdigit():
            return self.log(case_id, int(parts[4]), parts[5])
        raise FileNotFoundError(path)


@lru_cache(maxsize=6)
def view_data(path, _mtime, _case_id, physical, mesh):
    physical, mesh = json.loads(physical), json.loads(mesh)
    with np.load(path, allow_pickle=False) as arrays:
        surface = arrays["surface_xyz_m"] * 1000
        points = arrays["query_xyz_m"]
        velocity = arrays["velocity_m_s"][:, 2]
        grid = arrays["grid_sdf_m"]
        plane = grid[::2, ::2, grid.shape[2] // 2].T * 1000
        axis_x = arrays["grid_x_m"][::2] * 1000
        axis_y = arrays["grid_y_m"][::2] * 1000
    middle = points[np.argmin(np.abs(points[:, 2] - physical["LengthMm"] * .0005)), 2]
    central = np.abs(points[:, 2] - middle) <= 1e-8
    radius = np.linalg.norm(points[central, :2], axis=1) / math.cos(math.radians(mesh["halfAngleDeg"]))
    order = np.argsort(radius)
    ri, ro = (physical[key] * .001 for key in ("InnerRadiusMm", "OuterRadiusMm"))
    radii = np.linspace(ri, ro, 180)
    def analytical(samples):
        return [U_analytical(r, ri, ro, physical["PressureGradientPaPerM"],
                             physical["DynamicViscosityPaS"]) * 1000 for r in samples]
    si = np.linspace(0, len(surface) - 1, min(len(surface), 5600), dtype=int)
    qi = np.linspace(0, len(points) - 1, min(len(points), 1200), dtype=int)
    return {"surface": np.round(surface[si], 3).tolist(),
            "points": np.round(np.column_stack((points[qi] * 1000, velocity[qi] * 1000)), 4).tolist(),
            "plane": np.round(plane, 4).tolist(), "plane_x": axis_x.tolist(), "plane_y": axis_y.tolist(),
            "analytic": np.column_stack((radii * 1000, analytical(radii))).tolist(),
            "cfd": np.column_stack((radius[order] * 1000, velocity[central][order] * 1000,
                                    analytical(radius[order]))).tolist(),
            "radius_mm": physical["OuterRadiusMm"], "length_mm": physical["LengthMm"],
            "voxel_mm": physical["VoxelSizeMm"], "sector_deg": mesh["totalAngleDeg"]}


def handler(dataset):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, kind, body):
            self.send_response(status)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'self'; object-src 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}",
                                                 f"localhost:{self.server.server_port}"}:
                self.reply(403, "text/plain", b"Local host only")
                return
            path = unquote(urlsplit(self.path).path)
            if path in STATIC:
                file, kind = STATIC[path]
                self.reply(200, kind, (HERE / file).read_bytes())
                return
            try:
                body = json.dumps(dataset.route(path), allow_nan=False).encode()
                self.reply(200, "application/json", body)
            except FileNotFoundError as error:
                self.reply(404, "application/json", json.dumps({"error": str(error)}).encode())
            except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                self.log_error("%s", error)
                self.reply(503, "application/json", b'{"error":"Dataset artifact is unavailable"}')

        do_HEAD = do_GET

        def reject_write(self):
            self.reply(405, "text/plain", b"Read-only workspace")

        do_POST = do_PUT = do_PATCH = do_DELETE = reject_write

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--runs", type=Path, help="directory containing training run receipts")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = args.dataset.resolve()
    if not (root / "index.json").is_file():
        parser.error(f"no dataset index in {root}")
    runs = (args.runs or root / "runs").resolve()
    dataset = Dataset(root, runs)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler(dataset)) as server:
        print(f"SGK Workbench · http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
