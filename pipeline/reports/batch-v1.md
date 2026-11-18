# Annulus reference dataset batch v1

The batch used 20 new points from a four-dimensional Latin hypercube with seed
20261118. The split was frozen by normalized radius bands before execution.
The original pilot and Reynolds stress run were kept separate. Each voxel
retry inherits its physical point and split.

The first pass tested the declared geometry schedule of 0.20, 0.15, 0.10 and
0.075 mm. The runner stops before OpenFOAM if geometry fails. The additional
recovery plan records the reason for two targeted attempts. Numerical
acceptance thresholds remained unchanged.

- **Wide-gap edge case `ann-cc82c999`.** OpenFOAM completed the first run.
  Rounding the printed cell centres made one station appear twice and the
  validator rejected extraction. Grouping by expected mesh station counts
  with a tolerance of 1e-8 m fixed the issue. Replay and a fresh reference run
  passed. Both attempts remain in the index.
- **Narrow-gap edge case `ann-15e22abc` (0.601 mm nominal gap).** The best
  result in the original schedule missed the absolute volume limit of 0.1%,
  with an error of −0.1094% at 0.10 mm. At 0.05 mm the native runtime stopped
  with SIGSEGV before writing a VDB. The core shows `Library_nTotalMemUsage`
  traversing an OpenVDB tree while another thread was in
  `Voxels_BoolSubtract`. Concurrent traversal is a plausible cause. The
  root cause was not confirmed and the kernel journal records a segfault
  rather than an OOM kill. The rejected point has no CFD label.
- **Conversion probe `ann-7939f294`.** PicoGK reloaded the accepted VDB,
  supplied 45,096 surface vertices and a 48 × 48 × 32 narrow-band SDF grid.
  The probe maps 1,300 native CFD cell locations and vector values into the
  PicoGK frame. Core, wall, exterior and end-cap probes checked signs.
  Adjacent nodes at the outer wall checked distance units. The NPZ round trip
  reproduced the validated field integral of 3.373094705859089e-6 m³/s, with
  0.0203066% error against prescribed full-circle flow. Two executions
  reproduced every array exactly. This probe preserves native CFD sampling
  and does not set a final training grid or claim volume-wide conversion
  across all cases.

## Final index audit

The publication accounts for all 20 requested points and 30 attempts. It
contains 19 accepted CFD labels, with 11 in train, 4 in validation, 3 in test
and 1 in edge. The second edge case is explicitly rejected. Accepted voxel
sizes were 0.20 mm for 15 cases, 0.15 mm for 3 cases and 0.10 mm for 1 case.

The audit checked 6,466 artifact hashes across all attempts and verified that
accepted cases used the intended common solver settings. It replayed the
current validator on each accepted field, and independently summed the saved
outlet `phi` values. All accepted fields stayed below the 0.05% flow and 0.5%
pressure-gradient limits. The maximum gradient error was 0.05310%.

Twenty CFD runs occurred, including the wide-gap retry. OpenFOAM wall time
ranged from 30 seconds to 19 minutes and 28 seconds per run. The individual
wall times sum to about 79 minutes with overlap. The eight-worker execution
and targeted recovery took about 21 minutes from manifest write to the final
index on this host.

The canonical manifest and recovery plan are
[`batch-cases-v1.json`](../batch-cases-v1.json) and
[`batch-recovery-v1.json`](../batch-recovery-v1.json).
The local artifacts are in `~/data/datasets/sgk-mini/annulus-v1/`.
Read `index.json` for the selected record and all attempts per physical
point. Use the [runner and converter commands](../README.md) to reproduce
the batch and the one-case probe.

| Physical point | Split | Voxel (mm) | Flow native / field error (%) | Gradient error (%) | Result |
|---|---|---:|---:|---:|---|
| ann-66c4e299 | train | 0.2 | 0.02031 / 0.02031 | 0.00351 | accepted |
| ann-7939f294 | train | 0.2 | 0.02031 / 0.02031 | 0.00948 | accepted |
| ann-f1c115e0 | train | 0.2 | 0.02031 / 0.02031 | 0.00959 | accepted |
| ann-dce3a2fb | validation | 0.2 | 0.02031 / 0.02031 | 0.00942 | accepted |
| ann-2a6f96d1 | test | 0.2 | 0.02030 / 0.02031 | 0.00954 | accepted |
| ann-625c9fb9 | test | 0.2 | 0.02031 / 0.02031 | 0.00951 | accepted |
| ann-15e22abc | edge | 0.05 | — | — | rejected |
| ann-cc82c999 | edge | 0.2 | 0.02030 / 0.02031 | 0.00849 | accepted |
| ann-d4c1c5d6 | train | 0.2 | 0.02031 / 0.02031 | 0.00928 | accepted |
| ann-96018040 | validation | 0.2 | 0.02031 / 0.02031 | 0.00939 | accepted |
| ann-35ba0b7c | test | 0.2 | 0.02031 / 0.02031 | 0.00952 | accepted |
| ann-6f5c8a99 | train | 0.2 | 0.02031 / 0.02031 | 0.00571 | accepted |
| ann-4da45406 | validation | 0.2 | 0.02031 / 0.02031 | 0.00939 | accepted |
| ann-62e33943 | train | 0.15 | 0.02031 / 0.02031 | 0.00900 | accepted |
| ann-d80e8f87 | validation | 0.2 | 0.02031 / 0.02031 | 0.00934 | accepted |
| ann-5f657c98 | train | 0.15 | 0.02031 / 0.02031 | 0.00947 | accepted |
| ann-af094e34 | train | 0.1 | 0.02031 / 0.02031 | 0.00918 | accepted |
| ann-3d3194ee | train | 0.15 | 0.02031 / 0.02031 | 0.01479 | accepted |
| ann-555ceb7e | train | 0.2 | 0.02031 / 0.02031 | 0.00872 | accepted |
| ann-658eae93 | train | 0.2 | 0.02031 / 0.02031 | 0.05310 | accepted |
