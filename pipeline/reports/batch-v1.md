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
- **Narrow-gap edge case `ann-15e22abc` (0.601 mm nominal gap).** The 0.10 mm
  attempt missed the absolute volume limit of 0.1%, with an error of −0.1094%.
  At 0.05 mm PicoGK stopped with SIGSEGV before writing a VDB. The core
  shows `Library_nTotalMemUsage` on the background memory monitor while
  another thread was in `Voxels_BoolSubtract` and OpenVDB tree pruning.
  Concurrent traversal is the leading explanation. The kernel logged a
  segfault, with no OOM kill recorded in that interval. The surviving logs
  show that the viewer was active with `--auto-exit`. Intermediate trials at
  0.095 and 0.09 mm recovered the case at 0.09 mm, without modifying the
  runtime. The accepted volume error was −0.0497%, the reconstructed gap was
  0.600822 mm, and the gradient error was 0.201792%. The original crash and
  all rejected runs remain indexed.
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

The revised index accounts for 20 points and 32 attempts. All 20 have
accepted CFD labels: 11 train, 4 validation, 3 test and 2 edge. Accepted voxel
sizes were 0.20 mm for 15 cases, 0.15 mm for 3, 0.10 mm for 1 and 0.09 mm for 1.

The final audit checked 6,793 artifact hashes across all attempts and verified
the common solver settings. It replayed the current validator on each accepted
field and independently summed the saved outlet `phi` values. All accepted
fields stayed below 0.05% flow error and 0.5% pressure-gradient error. The
maximum gradient error was 0.201792% at the recovered narrow-gap point.

The first publication took about 21 minutes from manifest write to the index
on this host. Its 20 CFD executions, including the wide-gap retry, had wall
times of 30 seconds to 19 minutes and 28 seconds. The targeted narrow-gap
recovery was performed separately.

The batch manifest is [batch-cases-v1.json](../batch-cases-v1.json).
The original [recovery plan](../batch-recovery-v1.json) is preserved.
The [revised plan](../batch-recovery-v2.json) tries the intermediate pitches
before the finer 0.05 mm trial. A historical 0.05 mm attempt still appears in
the index even when the case can be accepted earlier.
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
| ann-15e22abc | edge | 0.09 | 0.02031 / 0.02031 | 0.20179 | accepted |
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
