#!/usr/bin/env python3
"""Create a feasible Latin hypercube for the eight-case annulus pilot.

Reject entire infeasible designs so each accepted design retains one point
per stratum in every dimension.
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(REPO, "pipeline", "pilot-cases-lhs.json"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--cases", type=int, default=N_CASES)
    parser.add_argument("--pool", type=int, default=POOL,
                        help="number of complete Latin hypercube designs to try")
    args = parser.parse_args()
    if args.cases < 2 or args.pool < 1:
        parser.error("at least two cases and one candidate design are required")

    rng = np.random.default_rng(args.seed)
    selected = None
    minimum = 0.0
    feasible_designs = 0
    for _ in range(args.pool):
        points = lhs(args.cases, rng)
        requests = [to_request(point) for point in points]
        if any(admissibility(request) for request in requests):
            continue
        feasible_designs += 1
        distance = min(
            normalized_distance(point, other)
            for i, point in enumerate(points)
            for other in points[:i]
        )
        if distance > minimum:
            selected = requests
            minimum = distance

    if selected is None or minimum < MIN_DISTANCE:
        raise SystemExit("no feasible Latin hypercube met the minimum distance")

    payload = {
        "schema": "sgk-mini.pilot-cases.v1",
        "seed": args.seed,
        "algorithm": (
            "Generate complete Latin hypercubes over [Ro, gap, L, log10(Q)]. "
            "Reject entire designs with inadmissible cases. Keep the feasible "
            "design with the greatest minimum normalized pairwise distance."
        ),
        "pool_size": args.pool,
        "feasible_designs": feasible_designs,
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
        "cases": [request.as_dict() for request in selected],
    }

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"written: {args.out}")
    print(f"candidate designs {args.pool}, feasible {feasible_designs}, "
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
