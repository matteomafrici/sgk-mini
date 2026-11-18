#!/usr/bin/env python3
"""Create the eight-case pilot design.

Latin hypercube over the four requested parameters, then feasibility filtering
against the coupled physical limits, then a maximin selection of eight cases.

The result is a *subset* of an LHS, not a strict LHS: rejecting infeasible
points and choosing a spread changes the stratification. The file records the
seed, the algorithm, the pool size, the bounds and the minimum pairwise
distance, so the claim can be checked instead of assumed.
"""

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annulus_case import Request, admissibility  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261118
N_CASES = 8
POOL = 400

BOUNDS = {
    "outer_radius_mm": (6.0, 20.0),
    "gap_mm": (0.6, 6.0),
    "length_mm": (10.0, 60.0),
    "flow_rate_m3_s": (1.0e-6, 3.0e-5),
}

MIN_DISTANCE = 0.05
VOXEL_MM = 0.2


def lhs(n, seed):
    """Latin hypercube in the unit cube. One stratum per dimension per point."""
    rng = np.random.default_rng(seed)
    points = np.empty((n, len(BOUNDS)))
    for j in range(len(BOUNDS)):
        strata = (np.arange(n) + rng.random(n)) / n
        points[:, j] = strata[rng.permutation(n)]
    return points


def to_request(point):
    ro = BOUNDS["outer_radius_mm"][0] + point[0] * (
        BOUNDS["outer_radius_mm"][1] - BOUNDS["outer_radius_mm"][0])
    gap = BOUNDS["gap_mm"][0] + point[1] * (
        BOUNDS["gap_mm"][1] - BOUNDS["gap_mm"][0])
    length = BOUNDS["length_mm"][0] + point[2] * (
        BOUNDS["length_mm"][1] - BOUNDS["length_mm"][0])
    q_low, q_high = BOUNDS["flow_rate_m3_s"]
    flow = 10.0 ** (
        math.log10(q_low) + point[3] * (math.log10(q_high) - math.log10(q_low)))
    return Request(ro, gap, length, flow, VOXEL_MM)


def normalized_distance(a, b):
    return float(np.linalg.norm(a - b))


def select(points, count):
    """Greedy maximin: start far from the pool mean, then maximise the minimum
    distance to the already selected points."""
    if len(points) <= count:
        return list(range(len(points)))

    centre = points.mean(axis=0)
    first = int(np.argmax([normalized_distance(p, centre) for p in points]))
    chosen = [first]

    while len(chosen) < count:
        best = None
        best_distance = -1.0
        for i in range(len(points)):
            if i in chosen:
                continue
            distance = min(normalized_distance(points[i], points[j]) for j in chosen)
            if distance > best_distance:
                best_distance = distance
                best = i
        chosen.append(best)

    return chosen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(REPO, "pipeline", "pilot-cases.json"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--cases", type=int, default=N_CASES)
    parser.add_argument("--pool", type=int, default=POOL)
    args = parser.parse_args()

    points = lhs(args.pool, args.seed)

    feasible_points = []
    feasible_requests = []
    rejected = {"gap below 3 voxels": 0, "inner radius below 3 voxels": 0,
                "Reynolds >= 2000": 0, "other": 0}

    for point in points:
        request = to_request(point)
        problems = admissibility(request)
        if problems:
            for problem in problems:
                if problem.startswith("gap"):
                    rejected["gap below 3 voxels"] += 1
                elif problem.startswith("inner radius"):
                    rejected["inner radius below 3 voxels"] += 1
                elif problem.startswith("Reynolds"):
                    rejected["Reynolds >= 2000"] += 1
                else:
                    rejected["other"] += 1
            continue
        feasible_points.append(point)
        feasible_requests.append(request)

    points = np.array(feasible_points)
    requests = feasible_requests

    if len(points) < args.cases:
        raise SystemExit(f"only {len(points)} feasible candidates for {args.cases} cases")

    chosen = select(points, args.cases)
    selected_points = points[chosen]
    selected = [requests[i] for i in chosen]

    distances = []
    for i in range(len(selected_points)):
        for j in range(i + 1, len(selected_points)):
            distances.append(normalized_distance(selected_points[i], selected_points[j]))
    minimum = min(distances) if distances else None

    if minimum is not None and minimum < MIN_DISTANCE:
        raise SystemExit(
            f"minimum normalized distance {minimum:.4f} is below {MIN_DISTANCE}; "
            "increase the pool or lower the case count")

    payload = {
        "schema": "sgk-mini.pilot-cases.v1",
        "seed": args.seed,
        "algorithm": (
            "Latin hypercube over [Ro, gap, L, log10(Q)] in the unit cube; "
            "feasibility filter; greedy maximin selection of the requested count. "
            "The result is a subset of an LHS, not a strict LHS after constraint "
            "handling."
        ),
        "pool_size": args.pool,
        "selected_count": len(selected),
        "bounds": BOUNDS,
        "voxel_size_mm": VOXEL_MM,
        "constraints": {
            "gap_min_mm": 3 * VOXEL_MM,
            "inner_radius_min_mm": 3 * VOXEL_MM,
            "reynolds_max": 2000,
            "note": "inner radius >= 3 voxels is an additional geometry-admissibility "
                    "bound: a radius below three voxels is not a measurement of the "
                    "requested shape.",
        },
        "minimum_normalized_distance": minimum,
        "duplicate_policy": (
            f"a normalized Euclidean distance below {MIN_DISTANCE} in the unit cube "
            "is treated as a near-duplicate and is not accepted"
        ),
        "grouping_policy": (
            "the normalized annular field depends only on Ri/Ro; Q scales it and L "
            "does not change it. Groups are therefore defined by round(Ri/Ro, 4). "
            "A future train/test split must keep a group intact; this pilot assigns "
            "no split because nothing is trained."
        ),
        "rejected_counts": rejected,
        "cases": [request.as_dict() for request in selected],
    }

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"written: {args.out}")
    print(f"pool {args.pool}, feasible {len(points)}, selected {len(selected)}, "
          f"min distance {minimum:.4f}")
    print(f"{'case':<14} {'Ro mm':>7} {'gap mm':>7} {'L mm':>7} {'Q m3/s':>11} "
          f"{'Ri mm':>7} {'Re':>7}")
    for request in selected:
        print(f"{request.case_id:<14} {request.outer_radius_mm:7.3f} "
              f"{request.gap_mm:7.3f} {request.length_mm:7.2f} "
              f"{request.flow_rate_m3_s:11.3e} {request.inner_radius_mm:7.3f} "
              f"{request.reynolds:7.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
