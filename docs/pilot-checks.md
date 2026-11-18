# Pilot checks: definitions and acceptance criteria

Written before implementation, per the audit instructions. Nothing here may be
adjusted after seeing results. If a criterion is wrong, the change and its reason
are recorded in the commit that changes it.

## Reference quantities

All analytical quantities come from the steady, fully developed, laminar,
incompressible annular Poiseuille solution for a concentric annulus with inner
radius `Ri`, outer radius `Ro`, length `L`, density `rho`, dynamic viscosity `mu`
and volumetric flow rate `Q`.

| Symbol | Definition |
|---|---|
| `A` | `pi (Ro^2 - Ri^2)`, the annulus cross-section |
| `Ubar` | `Q / A`, the mean axial velocity |
| `Dh` | `4 A / P` with `P = 2 pi (Ro + Ri)`; for an annulus this reduces to `2 (Ro - Ri)` |
| `Re` | `rho Ubar Dh / mu` |
| `dp/dx` | positive magnitude of the axial pressure gradient that drives `Q` |
| `Umax` | continuous maximum of the profile, evaluated where `du/dr = 0` |
| `r_peak` | `sqrt((Ro^2 - Ri^2) / (2 ln(Ro/Ri)))` |
| shear | `mu du/dr`, signed, in the same increasing-`r` coordinate at both walls |

The profile, with `dp/dx` positive in the flow direction:

```
u(r) = (dp/dx) / (4 mu) * [ Ro^2 - r^2 + (Ro^2 - Ri^2) ln(r/Ro) / ln(Ro/Ri) ]
```

These definitions are checked against an independent numerical integration of
radial momentum, not only against the production formula.

## Sector and full-circle flow

The reference case is a wedge of total angle `theta` about the axis.

- `Q_sector`: volumetric flux through an axial plane crossing the sector.
- `Q_full = Q_sector * (2 pi / theta)`.
- `A_sector = (theta / 2) (Ro^2 - Ri^2)`; `A_full = (2 pi / theta) A_sector`.
- The mesh is measured, not assumed: `A_mesh_sector = sum(V_cell) / L`, and the
  geometric defect is `(A_mesh_sector - A_sector) / A_sector`.

The tolerance on flow rate is stated against the **declared** `Q`, so a geometric
defect of the mesh appears as a flow-rate error. That is intentional: it forbids
hiding a wrong mesh behind a corrected area.

## Solver conservation

Reported separately, never merged:

1. `Q_in`, `Q_out`: signed native fluxes, from OpenFOAM's own `phi` summed on each
   axial cyclic patch (`surfaceFieldValue`, operation `sum`).
2. `imbalance = (Q_in + Q_out) / max(|Q_in|, |Q_out|)`, dimensionless.
3. `Q_field`: reconstructed from the saved velocity field using **cell volumes**
   divided by the length, so the weights come from the mesh and not from an
   assumed annulus.
4. `A_mesh_sector`: from the same cell volumes.

Acceptance: `|imbalance| < 1e-6` and `|Q_full - Q| / Q < 0.05 %`.

## Analytical comparison coordinates

- The comparison is made at **cell-centre radii**, with the analytical value
  evaluated at exactly the same radius. No extrapolation outside `[Ri, Ro]`.
- A cell whose centre falls outside `[Ri, Ro]` is reported and excluded, never
  clamped or shifted.
- The convention is recorded per case, because the mesh geometry decides whether
  the centre radius lies inside the analytical fluid domain.

Acceptance for the profile: mean absolute deviation below 1 % of `Umax` and
maximum below 2.5 % of `Umax`, at the middle axial station. These are engineering
targets for second-order finite volume on 100 graded radial cells; they are not
presented as a theoretical floor.

## Convergence

Reaching `endTime` is not convergence. A run is `converged` only if all of:

1. the final initial residual of `Ux` and of `p` is below the targets configured
   in `fvSolution` (`1e-5` and `1e-3`);
2. the transverse velocity is negligible in absolute terms,
   `max|Uy, Uz| / Umax < 1e-6` (their normalised residuals are unusable, because
   they normalise a field that is near zero);
3. the global continuity error is below `1e-6` of the inlet flux;
4. the observables are stable: `dp/dx`, `Q_in` and `Umax` change by less than
   `1e-5` relative between the last two saved times.

Otherwise the run is recorded as `iteration-limit` with its residual table, and
the case fails its reference acceptance. The failure stays in the index.

## Case identity and provenance

Every case is identified by a deterministic id derived from its parameters. A run
directory holds exactly one case; nothing is shared or overwritten between cases.

A record is published only when the stage that produces it succeeded. A failed
stage writes an explicit failure record with the diagnostics that explain it.

Each record carries:

- requested parameters, units and voxel size;
- reconstructed radii, volume and the geometry acceptance result;
- the solver dictionaries actually used;
- solver name and version, mesh cell count, and the mesh metadata used by the
  extraction;
- residuals, iterations and stopping reason;
- native fluxes, imbalance, field-integrated flow and mesh area;
- analytical comparison values and their coordinate convention;
- sha256 of every artifact it references.

File integrity (hashes) is not numerical reproducibility. Two runs on different
machines are expected to agree to the tolerances above, not bit for bit.
