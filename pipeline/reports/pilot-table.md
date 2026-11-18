# Annulus pilot — case table

Generated from the dataset records. Design: seed 20261118, pool 400, 8 cases, minimum normalized distance 0.8875.

No surrogate is trained. "Prediction" in this table is the CFD reference (and the geometry stage that feeds it); the analytical solution is the reference. The flow, dpL and profile columns are the measured errors against it.

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

## Acceptance criteria

Geometry: reconstructed radii and length within 10 um, volume error below 0.1 %, VDB round trip, requested and produced records agree.

Reference: guarded inputs, Mesh OK, finite fields, convergence criteria met, conservation imbalance < 1e-6, full-circle flow error < 0.05 %, pressure-gradient error < 0.5 %, profile mean < 1 % and max < 2.5 % of Umax.

## Failures

- ann-23451e5e: reference: Ux residual below target; p residual below target (or p field negligible); transverse velocity negligible; observables stable; convergence criteria met; pressure gradient; peak velocity; mean profile error; max profile error
- ann-35ea69f5: geometry: volume error below 0.1 %
- ann-8c4c0932: geometry: volume error below 0.1 %
- ann-d6d594b3: geometry: inner radius within 10 um; volume error below 0.1 %
