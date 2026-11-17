#!/usr/bin/env python3
"""Reproducible analytical check for sgk-mini (no extra dependencies).

Regenerates the geometry/feature/physics stage and compares the produced JSON
records against the committed golden files in validation/expected/.

Usage:
  scripts/check_analytic.py            # build + run + compare
  scripts/check_analytic.py --with-cfd # also run the OpenFOAM check (if available)

Exit code is non-zero if any value drifts beyond tolerance.
"""

import json
import math
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(REPO, "src", "SGK.Geometry")
DLL = os.path.join(PROJECT, "bin", "Debug", "net9.0", "SGK.Geometry.dll")
OUTPUT = os.path.join(REPO, "output")
EXPECTED = os.path.join(REPO, "validation", "expected")

REL_TOL = 1e-6
ABS_TOL = 1e-9

PAIRS = [
    ("hollow-cylinder.features.json", "features record"),
    ("hollow-cylinder.physical-case.json", "physical record"),
]


def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {cmd}")


def compare(path_actual, path_expected, label):
    with open(path_actual) as f:
        actual = json.load(f)
    with open(path_expected) as f:
        expected = json.load(f)
    problems = []
    _compare(actual, expected, label, problems)
    return problems


def _compare(a, b, path, problems):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            problems.append(f"{path}: key set differs ({sorted(set(a) ^ set(b))})")
        for k in set(a) & set(b):
            _compare(a[k], b[k], f"{path}.{k}", problems)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            problems.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _compare(x, y, f"{path}[{i}]", problems)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            problems.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            problems.append(f"{path}: {a!r} != {b!r}")
    else:
        if a != b:
            problems.append(f"{path}: {a!r} != {b!r}")


def main():
    with_cfd = "--with-cfd" in sys.argv

    run(["dotnet", "build", "src/SGK.Geometry/", "-c", "Debug"], cwd=REPO)
    run(["dotnet", DLL, "--auto-exit"], cwd=PROJECT)

    problems = []
    for name, label in PAIRS:
        problems += compare(
            os.path.join(OUTPUT, name),
            os.path.join(EXPECTED, name),
            label,
        )

    if problems:
        print(f"\nCHECK FAILED — {len(problems)} difference(s):")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nAnalytical check PASSED (all values within tolerance).")

    if with_cfd:
        run([os.path.join(REPO, "validation", "run_annulus.sh"), "--check"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
