# Pilot checklist

Status of the work requested for this task. Kept inside the repository so a
reviewer can see what was claimed and what was measured.

## Phase 1 — validation repair

- [x] Reject non-finite fields, metrics and forcing values. Negative test in
      `validation/test_guards.py`.
- [x] Compare at radial face radii, not raw cell centres inside the wall. The
      old 3.64/7.15 % profile error is gone; the claim that it was inherent
      second-order error is removed everywhere.
- [x] Integrate the field with the mesh cell volumes; read the native patch
      fluxes; report signed flux, conservation, sector flow, full-circle flow,
      field integral and area defect separately.
- [x] Check convergence: residuals, iterations, stopping reason, continuity,
      absolute transverse velocity, stability of dpL/Q/Umax. `endTime` alone is
      not convergence. The pressure residual is qualified with evidence.
- [x] Guard Ri, Ro, L, nu, the full Ubar vector and the case identity.
- [x] Clean stale time directories before a run; bind the report to the saved
      time and the log.
- [x] Strengthen the C# record: case id, output directory, per-case Q and fluid,
      unknown-property rejection, finite checks, transverse extents, record
      consistency, unimodal profile, signed shear convention.
- [x] Correct the documentation, including the removed causal claims.
- [x] Resolution sweep uses isolated output directories; `--write` preserves the
      handwritten prose.

## Phase 2 — D0

- [x] 2 degree axisymmetric wedge, one tangential cell, wedge patches.
- [x] Fixed acceptance: flow < 0.05 %, dpL < 0.5 %.
- [x] Measured: flow 0.0203 %, dpL 0.0095 %, profile 0.0046/0.0071 %.
- [x] The finite wedge's area defect is measured and reported, not assumed zero.

## Phase 3 — eight-case pilot

- [x] LHS design with seed 20261118, documented pool, feasibility filter,
      maximin selection and minimum distance.
- [x] Coupled constraints: gap, inner radius, Re, reconstructed geometry.
- [x] Deterministic case ids.
- [x] Per-case geometry, generated OpenFOAM case, reference run, checks, record,
      hashes and provenance.
- [x] Failed cases stay visible with reasons.
- [ ] Eight cases all passing: **not achieved.** Four pass, four fail for
      measured reasons (three geometry, one reference convergence/scheme).
- [ ] Full dataset: not generated, by instruction.

## Verification

- [x] `validation/test_guards.py`: wrong Ri, wrong L, wrong axial Ubar,
      transverse Ubar, wrong nu, swapped case id, NaN field, missing volumes.
- [x] Independent analytical reference by finite-difference radial momentum
      (temporary script, not committed): worst relative difference 6.3e-7.
- [x] `scripts/check_analytic.py` and `--with-cfd` run.
- [x] `scripts/voxel_resolution_curve.py` leaves the default output untouched.
- [ ] Case 2's scheme question is recorded as an open decision, not resolved by
      changing the certified scheme.

## Known limits

- The 10 um radius and 0.1 % volume criteria are not met at the lowest gaps.
  That is a measured property of 0.2 mm voxels on thin annuli, not a pipeline
  bug.
- The p residual and the absolute transverse criterion are close to the
  numerical noise floor at high Re. They are reported, not loosened.
