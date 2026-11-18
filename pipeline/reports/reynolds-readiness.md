# Reynolds convergence and dataset readiness

The original 80-cell axial mesh with bounded `limitedLinearV` failed at
Re ≈ 1790. Bounded `linearUpwind grad(U)` improved the pressure-gradient
error from 12.7445% to 0.009970% with the original linear-solver tolerance,
but the pressure and transverse-velocity checks still failed. Tightening the
linear-solver tolerance to 1e-10 on the same 80-cell mesh left a pressure
failure. The normalized pressure residual was 0.00529 against 0.001, and
the pressure magnitude ratio was 6.75e-9 against the negligible-pressure
threshold of 1e-9. The solver finished the 80-cell control. Its post-processing
was restarted separately after the launcher changed during that control run.

With eight axial cells on the same short, wide-gap annulus,
`linearUpwind` passed with either linear-solver tolerance. At 1e-10 the
gradient error was 0.006859%, and the native and saved-field flow errors
were both 0.020307%. The axial periodic reference is translation invariant.
Keeping the radial mesh and reducing axial cells was an appropriate
comparison for this reference. The result does not establish a general
mesh rule for developing flows.

Eight axial cells were insufficient for some longer cases. Their
`checkMesh` element determinant fell below the existing limit. The
production rule limits axial pitch to 65 times a conservative lower bound
on radial pitch, with a minimum of eight axial cells. For a gap split into
two equally sized radial blocks with reciprocal grading up to 1.5, that
lower bound is reconstructed gap divided by 1.5 times the total radial
cell count. The number 65 was selected for mesh quality margin in these
cases. `checkMesh` still checks the actual mesh. An injected D0 mesh with
eight axial cells was refused before `simpleFoam` started.

The new reference uses bounded `linearUpwind grad(U)` and a 1e-10
linear-solver tolerance. That tolerance increases numerical work. No
acceptance threshold changed.

A separate upper-edge run on the original high-Reynolds geometry used a
nominal Re of 1990 and reconstructed Re of 1989.70. All checks passed,
with gradient error 0.006859% and native and saved-field flow errors of
0.020305% and 0.020307%. Its imposed Q was 3.1932e-5 m³/s, slightly above
the pilot's sampling limit. This was a stress case near the Reynolds limit,
outside the eight-case design.

## Pilot definition

The executed design preserves all eight Latin hypercube points in the four
physical dimensions. Two of the eight geometries failed the 0.1% volume
criterion at 0.2 mm and passed at 0.15 mm. The executed manifest records
the two revised case IDs. Independent numerical integration of radial
momentum reproduced all eight analytical gradients to about 1e-10 relative.

Raw fields, mesh checks, reports, and the negative solver experiments are
under `~/data/datasets/sgk-mini/experiments/reynolds-heb6nhep/`.

```bash
validation/run_annulus.sh --check
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py \
  --cases pipeline/pilot-cases-lhs-refined.json \
  --root ~/data/datasets/sgk-mini/reynolds-pilot-reproduction \
  --reports ~/data/datasets/sgk-mini/reynolds-pilot-reports
```

Generate the default geometry with `scripts/check_analytic.py` before
running the first command from a clean checkout.

## Acceptance results

D0 passed from a clean build and solver run with 58 axial cells and 100 radial
cells. Its gradient error was 0.009537% and both flow errors were 0.0203%.
The geometry golden comparison and all ten guard tests passed.

The eight pilot meshes passed `checkMesh` with 8 to 48 axial cells.
All eight cases passed geometry, CFD and saved-field acceptance. The largest
observed pilot gradient error was 0.0775%, against the 0.5% limit. Both
flow errors were around 0.0203% for every case, against the 0.05% limit.
The native flow was independently reproduced by summing all eight saved
axial patch fluxes. All 2,560 listed artifact hashes matched.

The pilot supports starting the annular dataset with the existing per-case
checks and retaining failures. Its eight physical points and the upper-edge
stress run are evidence for the tested configurations. They do not show that
every sampled geometry will pass at the default voxel size or converge
throughout the full parameter box. The full batch has not been generated.
