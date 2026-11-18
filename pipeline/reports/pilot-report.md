# Annulus pilot — findings and handoff

Branch `codex/validation-repair-pilot`, HEAD `e66be2f` at the time of writing.
The audited baseline was `7ff4db0`; no intervening change existed before this
branch started.

This report is the English companion to the Italian completion message. It
records what was measured, not only what was built.

## 1. What was repaired before the pilot

The independent audit found four defects that a passing check could not see.
All are fixed and have a negative test (see `pipeline/CHECKLIST.md`):

1. A NaN velocity field produced five NaN metrics, `CHECK PASSED` and exit 0.
2. The profile was compared at the raw cell-centre radius of the innermost cell
   (7.976984 mm), which is inside the ideal wall (7.999342 mm). The analytical
   solution was being evaluated outside its domain.
3. The flow integral used invented edges at cell centres and one angular layer,
   reporting 0.7845 % where the native patch flux said 0.5069 %.
4. Convergence was never checked; reaching `endTime` counted as success.

The claim that a 3.64 % mean profile error was inherent second-order
finite-volume error was **wrong** and is removed from every document. With a
consistent comparison radius the error is 0.0046 % mean / 0.0071 % max on the
repaired case.

## 2. D0 — the reference case

The 30° section in three cells (0.507 % area defect) was replaced by a 2°
axisymmetric wedge in one tangential cell. A finite wedge still has a chord
defect of `sin(theta)/theta`; it is 0.0203 % at 2°, measured from the cell
volumes and reported, not assumed away.

Fixed acceptance, set before the run: flow < 0.05 %, dpL < 0.5 %.

| Quantity | Measured |
|---|---|
| full-circle flow error | **0.0203 %** |
| pressure-gradient error | **0.0095 %** |
| peak-velocity error | 0.0102 % |
| profile mean / max | 0.0046 / 0.0071 % |
| conservation imbalance | 0 |
| mesh sector-area defect | −0.0203 % |

The flow error and the measured area defect are the same number. The p field is
1.2e-12 of `dpL/rho·L`, so its normalised residual is not used; the qualification
and its evidence are in `docs/pilot-checks.md`.

## 3. Pilot design

- Seed 20261118, LHS over `[Ro, gap, L, log10 Q]`, pool 400, feasibility filter,
  greedy maximin selection of 8, minimum normalized distance 0.8875.
- The design is a **subset of an LHS**, not a strict LHS after constraint
  handling. This is recorded in `pipeline/pilot-cases.json`.
- Coupled constraints: gap ≥ 3 voxels (0.6 mm), inner radius ≥ 3 voxels,
  Re < 2000, plus the reconstructed-geometry checks.
- Grouping policy: the normalized field depends only on `Ri/Ro`; groups are
  `round(Ri/Ro, 4)`. No split is assigned because nothing is trained.
- A normalized distance below 0.05 is treated as a near-duplicate; the selected
  set's minimum is 0.8875.

## 4. Results

No surrogate is trained. "Prediction" below is the CFD reference; the analytical
solution is the truth it is compared against.

| Case | Ro (mm) | gap (mm) | L (mm) | Q (m3/s) | Re | flow err (%) | dpL err (%) | profile mean/max (%) | status |
|---|---|---|---|---|---|---|---|---|---|
| ann-073248ac | 6.514 | 1.540 | 21.71 | 1.029e-06 | 57.0 | 0.0203 | 0.0040 | 0.0076 / 0.0117 | ok |
| ann-0995b4f2 | 13.977 | 5.271 | 52.84 | 2.518e-05 | 706.8 | 0.0203 | 0.0093 | 0.0047 / 0.0083 | ok |
| ann-23451e5e | 7.938 | 5.661 | 14.04 | 2.872e-05 | 1790.1 | 0.0198 | 12.7445 | 5.2525 / 8.5674 | failed |
| ann-35ea69f5 | 19.308 | 1.263 | 23.42 | 2.042e-05 | 348.1 | 0.0203 | 0.0205 | 0.0112 / 0.0172 | failed |
| ann-38d5f169 | 9.044 | 3.973 | 58.05 | 1.739e-06 | 78.4 | 0.0203 | 0.0091 | 0.0047 / 0.0089 | ok |
| ann-8c4c0932 | 7.052 | 1.192 | 56.21 | 2.096e-05 | 1033.7 | 0.0203 | 0.0277 | 0.0128 / 0.0197 | failed |
| ann-d16c486a | 17.394 | 5.666 | 27.73 | 1.876e-06 | 41.0 | 0.0203 | 0.0094 | 0.0047 / 0.0078 | ok |
| ann-d6d594b3 | 18.657 | 0.628 | 58.67 | 1.236e-06 | 21.4 | 0.0203 | 0.1736 | 0.0446 / 0.0683 | failed |

Four pass, four fail. Every failure has a measured reason and keeps its record.

### Geometry failures (three cases)

| Case | gap (mm) | inner-radius error (µm) | volume error (%) |
|---|---|---|---|
| ann-d6d594b3 | 0.628 | 13.24 | +1.99 |
| ann-8c4c0932 | 1.192 | 0.62 | −0.176 |
| ann-35ea69f5 | 1.263 | 2.15 | −0.207 |

The 10 µm radius and 0.1 % volume criteria are not met below about 1.5 mm gap at
0.2 mm voxel. The 3-voxel rule (0.6 mm) is a *necessary* resolution bound, not a
sufficient accuracy bound. The crossover is between 1.26 mm (fails, 6.3 voxels)
and 1.54 mm (passes, 7.7 voxels). For the full batch, the design bound should be
raised to about 1.5–2 mm, or the 0.1 % criterion must be re-justified. The
criterion was not changed after seeing the result.

### Reference failure (one case)

`ann-23451e5e` (Re=1790, wide gap, short length) did not converge with the
certified `limitedLinearV` scheme in 8000 iterations: Ux residual 0.0054,
transverse velocity 8.0 % of Umax, dpL error 12.74 %, profile error 5.25/8.57 %.
The field was a limit cycle, not a slow transient.

A bounded experiment on the same case replaced the limiter with
`linearUpwind` (kept in `pipeline/reports/ann-23451e5e-linearUpwind.json`, full
log in the dataset's `experiments/` directory):

| Metric | limitedLinearV | linearUpwind |
|---|---|---|
| dpL error | 12.7445 % | **0.0100 %** |
| profile mean / max | 5.2525 / 8.5674 % | **0.0057 / 0.0164 %** |
| Ux residual | 0.0054 | 9.4e-7 |
| transverse / Umax | 8.0e-2 | 1.2e-6 |
| p residual | 0.228 | 0.681 |

The physical solution exists and is accurate; the bounded limiter is the cause
of the oscillation. The experiment was **not** adopted silently: the certified
scheme is unchanged. Adopting `linearUpwind` would require recertifying D0 and
the reference, and is an open decision. Even then, the `linearUpwind` run is
marginally above the pre-registered p-negative (6.5e-5 vs 1e-9) and transverse
(1.2e-6 vs 1e-6) thresholds; those thresholds are near the numerical noise floor
and should be reviewed with evidence, not loosened.

## 5. Independent analytical verification

A temporary script (`/tmp/opencode/sgk-independent.py`, not committed) solves the
radial momentum equation

```
mu (1/r) d/dr (r du/dr) = dp/dx
```

on a 200001-point finite-difference grid with both walls at rest, for a unit
gradient, then scales to the requested Q. It shares only the requested Q and the
reconstructed radii with the production formula.

Worst relative differences over the reference record and all eight pilot
records:

| Quantity | Worst relative difference |
|---|---|
| pressure gradient | 6.33e-7 |
| peak velocity | 2.71e-8 |
| peak radius | 0.011 µm |
| inner / outer wall shear | 1.2e-7 |
| 17 profile samples | 2.67e-8 |

The production formula is verified by a method that is not itself.

## 6. Injected failures

`validation/test_guards.py` breaks one thing at a time and requires rejection:

| Injected defect | Result |
|---|---|
| wrong inner radius | rejected |
| wrong length | rejected |
| wrong axial Ubar | rejected |
| transverse Ubar component | rejected |
| wrong kinematic viscosity | rejected |
| swapped case identity | rejected |
| NaN velocity field | rejected |
| missing cell volumes | rejected |

The preflight runs before `blockMesh`; a drifted case cannot reach the solver.

## 7. Reproduction

```bash
cd ~/Work/sgk-mini
dotnet build src/SGK.Geometry/ -c Debug

# reference case (D0)
./validation/run_annulus.sh --check

# guards
~/data/venvs/sgk-mini/bin/python validation/test_guards.py

# analytical + optional CFD
~/data/venvs/sgk-mini/bin/python scripts/check_analytic.py
~/data/venvs/sgk-mini/bin/python scripts/check_analytic.py --with-cfd

# design and pilot
~/data/venvs/sgk-mini/bin/python pipeline/sample_cases.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py --only ann-23451e5e
```

The pilot run is about 15 minutes on this machine. Individual cases are about
50–145 s of OpenFOAM.

## 8. Artifacts

- Design: `pipeline/pilot-cases.json`.
- Compact table: `pipeline/reports/pilot-table.md`.
- Machine index: `pipeline/reports/pilot-index.json`.
- Scheme experiment: `pipeline/reports/ann-23451e5e-linearUpwind.{json,txt}`.
- Full records and fields: `~/data/datasets/sgk-mini/<case-id>/`.
- Dataset index: `~/data/datasets/sgk-mini/index.json`.

Each `dataset-record.json` carries the request, both geometry records, the
reference report and checks, the mesh result, a sha256 manifest of every
artifact, and toolchain provenance.

## 9. Decisions and alternatives

1. **2° wedge, one cell.** Alternative: 30° in 3 cells (0.507 % defect) or 6
   cells over 30° (0.130 %). Chosen because it is both more accurate and
   cheaper; the finite-wedge defect is measured, not assumed zero.
2. **Radial cell size near 20 µm, adaptive count.** Alternative: 100 cells for
   every gap. Rejected because 6 µm cells at a 0.6 mm gap are flagged by
   checkMesh as under-determined and add no information.
3. **Adaptive case generation by copying the certified dictionaries.** Alternative:
   a general template engine. Rejected as unnecessary abstraction; the changed
   literals are in one function and are re-guarded.
4. **Keep the failed cases and the certified scheme.** Alternative: switch to
   `linearUpwind` and rerun the pilot until everything passes. Rejected because
   it would hide both the geometry limit and the scheme defect.
5. **Pressure residual judged with a negligibility qualification.** Alternative:
   require the normalised value unconditionally, which is unattainable because
   the field is numerically zero. The qualification is recorded with the
   measured ratio, not used to hide a non-converged field.

## 10. Uncertainty

- Whether the Re=1790 failure is purely the limiter or also a physical
  transition cannot be decided from one case. The `linearUpwind` run produced a
  clean axisymmetric solution, which points to the limiter, but the Re range
  near 1800 should be explored before the full batch.
- The 1.5 mm geometry bound is inferred from three failures and one pass; it is
  not a measured curve. A small gap sweep would make it a measurement.
- The p and transverse thresholds are at the numerical noise floor. They are
  reported as failures rather than relaxed; a principled tolerance derived from
  the pressure scale and the machine precision is still missing.
- Nothing here says anything about surrogate accuracy: no model was trained.

## Current state

- Branch `codex/validation-repair-pilot`, work committed on top of `7ff4db0`.
- D0 passes its fixed criteria; the reference case is a 2° wedge.
- The pipeline runs eight requested cases; four pass and four fail with records.
- The independent analytical check agrees to 6.3e-7.
- The full dataset has not been generated.

## Decisions made

- Wedge reference, adaptive radial cells, copied certified dictionaries,
  failed-case visibility, and a qualified pressure residual.
- The `linearUpwind` experiment is evidence, not an adopted setting.

## Next steps

1. Decide the gap lower bound for the full batch: 1.5 mm is the first measured
   passing value; 2 mm would leave margin.
2. Decide the scheme question: recertify D0 with `linearUpwind`, or restrict the
   Re range, or document the certified scheme's limit.
3. Re-derive the p and transverse tolerances from the pressure scale and the
   noise floor, before seeing more cases.
4. Run a small gap/Re sweep to replace the inferred bounds with measurements.
5. Only then generate the full batch, and keep the failure index.

## Knowledge base updates

- The vault decision note should record the D0 result, the geometry limit near
  1.5 mm, and the limiter finding.
- `validation/README.md`, `README.md` and `docs/dataset-pipeline.md` are updated
  in the repository; the vault note is read-only for this task and was not
  modified.

## Open questions

- Is the Re=1790 limit cycle a limiter artefact only, or does the annular flow
  become unsteady before Re=2000 at wide gaps?
- What is the honest lower gap bound for 0.2 mm voxels: 1.5 mm, 2 mm, or a
  per-case check with a documented failure policy?
- Should the certified scheme be changed for the whole dataset, and if so, does
  D0 still meet its criteria?
