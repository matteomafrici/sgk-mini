# SGK Mini

This is a small companion project of SGK — Space Generative Kernel (see the `sgk` repository). Its only job is to check, on a deliberately small case, that the technical stack the SGK pre-design relies on actually stands up, before investing engineering time in the full architecture.

The scope is intentionally narrow: a hollow cylinder, an analytical flow benchmark, and a CFD cross-check. Nothing here pretends to be more than that.

## What is in this repository

- `src/SGK.Geometry/` — the C# / .NET 9 project (the whole codebase).
- `SGK-Mini.sln` — solution file.
- `output/` — generated geometry and JSON records (gitignored).
- `cases/` — the OpenFOAM case files and validation scripts used for the CFD cross-check. They are kept locally, outside the repository; the numbers they produced are listed below.

## Environment

- Fedora 44 (native development environment).
- .NET 9 SDK.
- PicoGK 2.2.0 (NuGet package). PicoGK's native runtime has no official Linux binary; it was built from source on this machine (CMake + GCC, OpenVDB/GLFW/imgui via git submodules, Blosc built separately) and the resulting `picogk.so` is copied into the build output with the symlink naming the P/Invoke layer expects. This artifact is machine-specific and not versioned — it must be rebuilt on any new machine.

## Build and run

```bash
dotnet run --project src/SGK.Geometry/
```

Requires the .NET SDK and the PicoGK native runtime as described above.

## What has been validated

- PicoGK voxel geometry generation and round-trip serialization to `.vdb` on Fedora 44 / .NET 9, with the native runtime built from source.
- A minimal hollow-cylinder geometry (OD 20 mm, ID 16 mm, length 50 mm), with feature extraction and JSON round-tripping through two independent code paths (schema identity plus minimal numeric sanity checks).
- An analytical physics benchmark: steady, fully developed laminar axial water flow in a concentric annulus, with both global targets (mean velocity, Reynolds number, pressure gradient and drop) and local targets (velocity profile, maximum velocity, wall shear stress on both walls).
- OpenFOAM `simpleFoam` validated against that analytical benchmark on two geometric configurations:
  - narrow gap (Ri = 8 mm, Ro = 10 mm, Re ≈ 35);
  - wide gap (Ro = 30 mm, Re ≈ 17), as a sensitivity test.
  - Recommended mesh: cyclic periodic boundary conditions with `meanVelocityForce`, 80 × 100 × 3 cells, radial grading 1.5.
  - Results: peak velocity (Umax) error 0.023%, pressure-gradient error 0.74%, flow-rate error 0.86%, mean near-wall profile error 3.6% — as far as I can tell, the near-wall error is systematic and inherent to second-order finite-volume discretization at this aspect ratio, not an implementation defect.

## What is missing

- a small (geometry, CFD field) dataset;
- training of a first tiny PhysicsNeMo surrogate and testing its inference accuracy and speed against the analytical/CFD ground truth;
- a minimal Layer 3 optimization loop.

## How this feeds SGK

The SGK pre-design describes four layers; only an embryo of Layer 1 exists, and it is here. If this validation slice holds, SGK proper starts from a small but complete problem — a liquid engine in blowdown mode, for example — and grows family by family. This repository stays as a validation record; what is learned here gets rewritten cleanly into `sgk`.