# SGK Mini

This is a small companion project of SGK — Space Generative Kernel (see the `sgk` repository). Its only job is to check, on a deliberately small case, that the technical stack the SGK pre-design relies on actually stands up, before investing engineering time in the full architecture.

The scope is intentionally narrow: a hollow cylinder, an analytical flow benchmark, and a CFD cross-check. Nothing here pretends to be more than that.

## Results at a glance

The validation compares OpenFOAM against the exact annular-Poiseuille
solution. The figures below are committed in the repository, so you can read
them without cloning or running anything.

**Values — CFD against analytical** (annulus Ri=8.00 mm, Ro=10.00 mm, Re≈35,
80×100×3 cells, 2000 iterations):

![validation values](validation/figures/04_metrics_summary.png)

**Radial velocity profile** at three axial stations — the flow is fully
developed, so the profile is the same everywhere:

![velocity profile](validation/figures/01_velocity_profile.png)

**Axial velocity field** on the meridional plane (CFD, analytical, and their
difference — the residual is the systematic near-wall finite-volume bias):

![velocity field](validation/figures/02_fields_velocity.png)

**Pressure drop** along the annulus (the raw CFD pressure is periodic because
the driving gradient lives in the `meanVelocityForce` source term; the linear
part is reconstructed with the solver's own gradient):

![pressure drop](validation/figures/03_pressure.png)

## What is in this repository

- `src/SGK.Geometry/` — the C# / .NET 9 project (the whole codebase).
- `SGK-Mini.sln` — solution file.
- `output/` — generated geometry and JSON records (gitignored).
- `validation/` — the reproducible validation: the OpenFOAM case (dictionary
  sources only), `validate_annulus.py`, `run_annulus.sh`, and the expected
  records. See `validation/README.md`.
- `scripts/check_analytic.py` — one-command analytical check (build, run,
  compare against `validation/expected/`).
- `scripts/voxel_resolution_curve.py` — measures the geometry stage at several
  voxel sizes (time, memory, volume convergence) and writes
  `validation/voxel-resolution-curve.md`.
- `cases/` — local, exploratory OpenFOAM cases and historical scripts used
  while developing the validation. Kept locally, outside the repository.

## The test case

| Parameter | Value |
|---|---|
| Nominal outer / inner diameter | 20 mm / 16 mm |
| Nominal length | 50 mm |
| Voxel size | 0.2 mm |
| Density | 1000 kg/m³ |
| Dynamic viscosity | 0.001 Pa·s |
| Volumetric flow rate | 1e-6 m³/s |
| Velocity profile samples | 17 radial locations, both walls included |
| Reynolds number | ≈ 35.4 |

The flow assumptions are steady, incompressible, Newtonian, laminar, fully
developed axial flow in a concentric annulus, with no-slip walls and entry and
exit effects neglected.

The analytical model does not use the nominal radii directly: it reconstructs an
equivalent annulus from the measured voxel volume and bounding box (area =
volume / length). The reconstruction is honest but not exact, so the radii it
works with differ slightly from the nominal ones — Ri = 7.9993 mm and
Ro = 10.0000 mm in the reference run at 0.2 mm voxel, against a nominal 8 mm and
10 mm. The residual is 0.7 µm, about 0.004 voxel.

## Outputs

Everything generated lands in `output/`, which is gitignored:

| File | Contents |
|---|---|
| `hollow-cylinder.vdb` | voxel field, saved and reloaded for the round-trip check |
| `hollow-cylinder.features.json` | schema and case identifiers, volume, bounding box |
| `hollow-cylinder.physical-case.json` | reconstructed radii, fluid properties, mean velocity, Reynolds number, pressure gradient and drop, 17 velocity samples, continuous and sampled peak velocity, wall shear stresses |

## Environment

- Omarchy 4.5 (Arch-based), native development environment.
- .NET 9 SDK.
- PicoGK 2.2.0 (NuGet package). PicoGK's native runtime has no official Linux
  binary; it is built from source (CMake + GCC, OpenVDB/GLFW/imgui via git
  submodules, system Blosc) and the resulting `picogk.so` is copied into the
  build output next to the symlink names the P/Invoke layer expects. This
  artifact is machine-specific and not versioned — it must be rebuilt on any
  new machine. See the `sgk-mini` notes in the vault for the exact procedure.
- OpenFOAM v2606 (core) for the CFD cross-check, available via its `etc/bashrc`.

## Build and run

```bash
dotnet run --project src/SGK.Geometry/ -- --auto-exit
```

Flags:

- `--auto-exit` — close the PicoGK viewer automatically when the task ends
  (needed for scripts/CI; without it the viewer stays open until closed).
- `--config <file.json>` — override the geometry, e.g.
  `{ "OuterRadiusMm": 12.0, "InnerRadiusMm": 9.0, "LengthMm": 40.0,
  "VoxelSizeMm": 0.2 }`.
  Defaults reproduce the validated 20/16 mm × 50 mm hollow cylinder at 0.2 mm
  voxel. `VoxelSizeMm` is a case parameter because it bounds which features the
  geometry can represent: a feature needs a few voxels across to be honest, so
  at 0.2 mm nothing below about 0.6 mm is resolved. See
  `validation/voxel-resolution-curve.md` for the measured trade-off.

Output always lands in the repository's `output/` directory, regardless of the
working directory the program is launched from.

## Reproduce the validation

```bash
./scripts/check_analytic.py          # build + run + compare (no OpenFOAM needed)
./scripts/check_analytic.py --with-cfd   # add the OpenFOAM cross-check
```

or, manually:

```bash
dotnet run --project src/SGK.Geometry/ -- --auto-exit
./validation/run_annulus.sh --check
```

## What has been validated

- PicoGK voxel geometry generation and round-trip serialization to `.vdb` on
  Linux / .NET 9, with the native runtime built from source.
- A minimal hollow-cylinder geometry (OD 20 mm, ID 16 mm, length 50 mm), with
  feature extraction and JSON round-tripping through two independent code paths
  (schema identity plus minimal numeric sanity checks).
- An analytical physics benchmark: steady, fully developed laminar axial water
  flow in a concentric annulus, with both global targets (mean velocity,
  Reynolds number, pressure gradient and drop) and local targets (velocity
  profile, maximum velocity, wall shear stress on both walls).
- OpenFOAM `simpleFoam` validated against that analytical benchmark on two
  geometric configurations:
  - narrow gap (Ri = 8 mm, Ro = 10 mm, Re ≈ 35);
  - wide gap (Ro = 30 mm, Re ≈ 17), as a sensitivity test.
  - Recommended mesh: cyclic periodic boundary conditions with
    `meanVelocityForce`, 80 × 100 × 3 cells, radial grading 1.5.
  - Results at 0.2 mm voxel: peak velocity (Umax) error 0.28%, pressure-gradient
    error 1.04%, flow-rate error 0.50%, mean near-wall profile error 3.65%.
    The flow-rate error is fully explained by the angular discretisation: three
    cells over a 30° wedge make a polygonal cross-section with 0.507% less area
    than the annulus. The near-wall profile error is systematic and inherent to
    second-order finite-volume discretization at this aspect ratio.
  - The previous, better-looking numbers (0.011% / 0.74% / 0.79%) were measured
    at 0.3 mm voxel, where the reconstructed radii were 3 µm off and partly
    cancelled the mesh bias. Accurate geometry exposes the solver's own error
    instead of hiding it.
- This validation is reproducible from the repository: the cyclic case lives in
  `validation/openfoam/annulus_cyclic/`, and `scripts/check_analytic.py`
  regenerates and checks the analytical records against committed expectations.

## What was corrected on 2026-11-17

Three defects previously listed here are closed, and the physical record schema
moved to `sgk-mini.physical-record.v2` to mark the change:

- **Domain wording.** `GeometryInterpretation` no longer calls the voxel body
  "the solid wall of the annular flow passage". It now states what the code
  actually does: the voxel body is the wall material between the inner and outer
  radius, its volume and bounding box are used only to recover those radii, and
  the fluid domain is the annular space between them. No fluid region is
  extracted from the geometry.
- **Peak velocity.** `MaxVelocityMPerS` is now the continuous analytical maximum,
  evaluated where `du/dr = 0`, instead of the largest of the 17 profile samples.
  The sampled value is still recorded, as `SampledMaxVelocityMPerS` and
  `SampledMaxVelocityRadiusMm`, and the record validator asserts that it cannot
  exceed the continuous maximum. This moved the peak-velocity error against CFD
  from 0.023 % to 0.011 % at the then-current 0.3 mm voxel size; at 0.2 mm the
  mesh discretisation dominates instead, and the measured error is 0.28 %.
- **Exit status.** A failure now exits non-zero. Exceptions raised inside the
  PicoGK task thread are captured there, since an exception escaping that thread
  is not guaranteed to reach the outer handler. Verified on two paths: a geometry
  smaller than one voxel (`Invalid volume: 0`) and an invalid `--config`.

## What remains open

- The mesh still represents the annulus as a 30° wedge in three cells, so its
  cross-section is a polygon with 0.507 % less area than the real annulus. This
  is now measured instead of hidden, but it is a systematic bias in the
  reference labels. A 2D axisymmetric (`wedge`) mesh would remove it and cost a
  third of the cells.
- The reconstructed radii still differ from the nominal ones by 0.7 µm at
  0.2 mm voxel. That residual is the discretisation of the representation, and
  it is reported rather than corrected.

## What is missing

- The geometry is not yet consumed by the physics: the annular benchmark is
  reconstructed from scalar features (bbox + volume), not from the voxel field,
  and the CFD case is a hand-built annulus. The geometry→physics coupling is
  currently nominal.
- A dataset generator. The geometry is parameterizable, but nothing yet samples
  that parameterization into a dataset.
- A small (geometry, CFD field) dataset.
- A first tiny surrogate (PhysicsNeMo), with its inference accuracy and speed
  measured against the analytical and CFD ground truth.
- A minimal Layer 3 optimization loop.

## Planned: dataset and surrogate validation

Everything below is **planned, not implemented**. It exists here so the target is
written down before the work starts, and so the acceptance criteria cannot be
chosen after seeing the results.

### What is being validated

Seven boundaries, each with a test that can fail. A boundary that is not tested
is a claim, not a capability.

| # | Boundary | Acceptance criterion |
|---|---|---|
| 1 | voxel geometry → CFD mesh | the mesh reproduces the voxel volume and radii within a declared tolerance, and the difference is explained by snapping and grading; a full CFD case runs from the geometry alone |
| 2 | CFD → dataset | every run stores residuals, iterations, mass balance and the analytical cross-check; failed runs are kept but never used as labels |
| 3 | geometry → model input | one converter for training and inference; the distance-field round trip is verified; normalization is saved with the model |
| 4 | model → physics | errors on engineering quantities and on the field, on geometries held out of training, reported alongside the loss |
| 5 | model → search | every selected candidate is recomputed with the reference solver; predicted versus reference is reported |
| 6 | geometry → printable artifact | watertight solid, declared minimum wall and channel respected, voxel resolution sufficient for the features claimed |
| 7 | results → conclusions | the metrics are read against written criteria, and the irreducible error of the reference (about 3.6% near the wall) is separated from model error |

### Target and baselines

The **field** is the real target: predicting the velocity map over the passage,
not only the two integrated numbers. Engineering quantities (pressure gradient,
peak velocity) stay as a minimum score every model must pass, and as a cheap
reference.

Three models are compared on identical splits, and the comparison has a declared
purpose:

- a **parameter-only regressor** — not a rival, but a threshold: it tells how
  much of the error is irreducible on this family of shapes;
- a **fixed-grid operator** — the cheap operator baseline;
- a **geometry-aware model** — the candidate, certified rather than ranked.

### Certification of the geometry-aware model

On this case the exact answer is known, so the model is checked, not just scored:

- **accuracy** against the analytical and CFD references;
- **invariance**: the same case described differently (shifted origin, rotated
  axis, denser surface sampling) must give the same answer;
- **mass balance**: the predicted velocity field must integrate to the imposed
  flow rate;
- **domain edges**: thin gaps, high eccentricity and out-of-range parameters must
  degrade predictably, not explode.

Before any of these is trusted, the checks themselves are broken on purpose: an
injected error must be detected. A check that cannot fail proves nothing.

### Resolution rule

The voxel size is a case parameter, not a constant, and the default is 0.2 mm.
A feature is represented honestly only at a few voxels across; at 0.2 mm,
features below about 0.6 mm are not resolvable. The dataset bounds must respect
that rule, and the coarse/fine resolution split (search versus final
verification) follows from it.

### What this stage will not claim

- It will not show that geometry matters. On a full engine that is already given;
  the annular case cannot demonstrate it.
- It will not show that a learned model replaces the reference solver. Only that
  it approximates it within a measured error and a measured cost.
- It will not judge a design search on speed alone: benefit is measured at
  comparable design quality.

## How this feeds SGK

The SGK pre-design describes four layers; only an embryo of Layer 1 exists, and it is here. If this validation slice holds, SGK proper starts from a small but complete problem — a liquid engine in blowdown mode, for example — and grows family by family. This repository stays as a validation record; what is learned here gets rewritten cleanly into `sgk`.
