# Follow-up on the annulus pilot

The pilot tests whether a requested geometry, a saved CFD field and the
analytical reference agree. Both full-circle flow estimates now have to meet
the existing 0.05% limit. Reducing axial velocities by 0.2% in memory left the
native flow error at 0.02031% and raised the saved-field error to 0.22027%. The
updated validator rejected the case. OpenFOAM's global continuity diagnostic is
now converted to an equivalent sector flux before comparison to a flux.

The original D0 run at commit 24834a9 was replayed with the updated checks.
The native and field flow errors were 0.020307% and 0.020306%. The gradient
error was 0.009537%. All ten negative guards passed. Replaying the original
eight cases kept the original four passes and four failures.

Each retry now has its own directory. In a fault test, two attempts of the same
inadmissible request remained in the index with separate failure records.
Records carry the assembly fingerprint and the tracked source patch. The new
eight-point design fills each of the eight strata in all four dimensions. It
regenerates byte-for-byte from the recorded seed. Its cases were not used for
this follow-up, which deliberately repeats known failures.

## Voxel resolution

The nominal radii, length and flow were held fixed. The original voxel size
was 0.20 mm. Errors below are signed volume errors against nominal volume.
The limits remain absolute volume error below 0.1% and radius errors at most
10 µm. The selected sizes were the coarsest of the tested sizes that passed
the geometry checks.

| Original case | Gap (mm) | 0.20 mm | 0.15 mm | 0.10 mm | Selected voxel (mm) |
|---|---:|---:|---:|---:|---:|
| ann-35ea69f5 | 1.263 | −0.2071% | −0.0083% | −0.0229% | 0.15 |
| ann-8c4c0932 | 1.192 | −0.1756% | −0.0095% | +0.0532% | 0.15 |
| ann-d6d594b3 | 0.628 | +1.9851% | −0.4695% | +0.0835% | 0.10 |

Both wider gaps passed at 0.15 mm. For the narrowest gap the inner-radius
error fell from 13.2362 µm at 0.20 mm to 0.6644 µm at 0.10 mm. Volume error
was non-monotone for the other two cases. A finer voxel size is therefore
checked for each geometry instead of assumed to be more accurate.

## Solver comparison

The comparison changed only the convection scheme, from bounded
`limitedLinearV 1` to bounded `linearUpwind grad(U)`. D0 passed with the
experimental scheme. Its gradient and both flow errors agreed with the
baseline to the reported precision.

For ann-23451e5e, at Re ≈ 1790, the pressure-gradient error fell from
12.7445% to 0.009970%. The profile errors fell to 0.005651% mean and
0.016372% max. This run still failed the pressure criterion and the
transverse-velocity criterion. The transverse ratio was 1.203e-6 against
a 1e-6 limit. The pressure residual was 0.681 and the dimensionless
pressure magnitude was 6.502e-5, above the negligible-pressure allowance.
The working reference scheme and all acceptance thresholds were retained.

## Refined cases through CFD

All three selected configurations passed end to end at commit `13ba5e9`
with a clean working tree. Results use the original `limitedLinearV`
reference scheme.

| Original case | Refined case | Native / saved-field flow error (%) | Gradient error (%) |
|---|---|---:|---:|
| ann-35ea69f5 | ann-3af2a71f | 0.020304 / 0.020306 | 0.020511 |
| ann-8c4c0932 | ann-2f46aa8b | 0.020303 / 0.020307 | 0.027651 |
| ann-d6d594b3 | ann-832ef007 | 0.020306 / 0.020306 | 0.173630 |

The complete experiment directory is
`~/data/datasets/sgk-mini/experiments/review-q4k2vmuo/`. It contains
`refined-cases.json`, the source of the three-case follow-up,
`refined-pilot/index.json`, the geometry-only measurements for all six voxel
trials, and the two `linearUpwind` solver runs with their dictionaries and logs.

To repeat the three cases in a separate directory from the repository root:

```bash
experiment=~/data/datasets/sgk-mini/experiments/review-q4k2vmuo
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py \
  --cases "$experiment/refined-cases.json" \
  --root "$experiment/reproduction" \
  --reports "$experiment/reproduction-reports"
```

For a solver comparison replay, copy the three dictionary directories and
`case.json` to a fresh case directory, keep the matching physical record, and
set `CASE_DIR` and `BENCHMARK` when invoking
`validation/run_annulus.sh --check`. The archived dictionaries show the
exact convection-scheme change.

## Handoff

- Current state. D0 passes, the original pilot remains intact, and the three
  geometric failures pass after per-case refinement. The high-Reynolds
  reference still fails its convergence checks.
- Decisions made. Keep the original thresholds and reference scheme. Keep the
  0.6 mm lower gap bound even when a case uses a finer voxel grid. Keep the
  strict Latin hypercube design separate from the targeted retests.
- Next steps. Resolve the high-Reynolds solver failure or define and verify a
  narrower reference domain. Run the strict eight-case design within that
  certified domain before starting a full batch.
- Knowledge base updates. The local evidence is in this report and the
  experiment directory. The vault can reference this evidence after review.
- Open questions. Three case-specific refinements cannot establish a universal
  voxel resolution. D0 and one high-Reynolds comparison cannot certify a
  replacement convection scheme across the operating range.
