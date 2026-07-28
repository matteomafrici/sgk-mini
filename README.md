# SGK Mini

## Purpose

SGK Mini is a minimal, disposable validation slice of the SGK (Space Generative Kernel)
project. Its goal is to prove that the real technical stack works end-to-end on a
small, controllable case, before any serious engineering time is invested in the full
SGK architecture.

This is NOT a demo. This is NOT the production repository. This is a throwaway proof
of concept: once the stack is validated, the knowledge gained here gets rewritten
cleanly into the `sgk` repository. Code quality bar here favors speed and honesty
over elegance.

## What SGK is (context)

SGK generates 3D propulsion engine geometry from physical equations (Layer 1), predicts
its physical behavior via neural surrogate models instead of full CFD (Layer 2), and
optimizes design through generative search (Layer 3), eventually driven by natural
language (Layer 4).

## Scope of SGK Mini

SGK Mini validates the full pipeline end-to-end, not just Layer 1. Layer 1 comes
first because every later layer depends on it, but the validation target includes
the whole chain on a deliberately tiny case:

1. Geometry generation (Layer 1 embryo, PicoGK).
2. Feature extraction from geometry.
3. A minimal physical case with analytical ground truth.
4. A small dataset built from (geometry, physics) pairs.
5. Training of a tiny surrogate model (Layer 2 embryo).
6. Inference on a test case.
7. A minimal optimization loop (Layer 3 embryo).
8. End-to-end integration check across every layer boundary.

Each step above only starts once the previous one is proven. The exact scope and
order can be refined as we learn — this list is the current plan, not a rigid
contract.

## Explicit non-goals

- No realistic engine geometry yet (convergent-divergent nozzle comes after the
  cylinder embryo is validated).
- No premature abstractions (no `EngineBase` class hierarchy yet).
- No Layer 4 (natural language interface) — out of scope for Mini entirely.

## Environment

- Fedora 44 (native development environment).
- .NET 9 SDK.
- PicoGK 26.2.0 native runtime, built from source on this machine
  (leap71/PicoGKRuntime has no official Linux binaries — only macOS/Windows).
  Build details: CMake + GCC 16.1.1, OpenVDB/GLFW/imgui via git submodules,
  Blosc 1.21.7 built separately from source and installed to `/usr/local`.
  Native `picogk.so` is copied (with symlinks matching the `picogk.26.2`
  naming expected by the .NET P/Invoke layer) into
  `src/SGK.Geometry/bin/Debug/net9.0/`. This artifact is machine-specific
  and NOT versioned in this repo (see `.gitignore`) — it must be rebuilt on
  any new clone/machine following the build notes archived in the SGK vault.

## Working principles (antirez style)

- Simplicity first: the simplest solution that answers the current validation
  question wins.
- One task at a time: each session in this repo closes one small, verifiable step.
- Validation before expansion: no new layer/feature until the current one is proven.
- Code as documentation: clear names, no enterprise patterns, minimal comments with
  actual purpose.

## Relationship to the main SGK repository

This repo does not get merged into `sgk` via Git history. When validation is
complete, working knowledge (what worked, what didn't, what the real integration
constraints are) gets distilled into clean code inside `sgk`. This repo remains
archived as a historical reference, clearly marked as validation-only.

## Repository structure (current, minimal)

```text
sgk-mini/
├── README.md
├── .gitignore
├── output/
│   ├── hollow-cylinder.vdb
│   ├── hollow-cylinder.features.json
│   └── hollow-cylinder.physical-case.json
└── src/
    └── SGK.Geometry/
        ├── Program.cs
        └── SGK.Geometry.csproj
```

This structure is intentionally minimal. It will grow only as validation goals are
checked off — not in anticipation of future needs.

---

## Current status

**Last updated:** 2026-07-28

### Validation checklist

- [x] Repo builds and runs from a clean clone (native PicoGK runtime built
  separately, not versioned — see Environment section).
- [x] C# + PicoGK integration works (voxel geometry generated, viewer
  rendered and interactively orbitable).
- [x] Minimal hollow-cylinder geometry generated (OD 20 mm, ID 16 mm, length 50 mm).
- [x] Geometry serialized to `.vdb`, reloaded, and validated by voxel equality.
- [x] Minimal feature extraction from geometry.
- [x] Feature record written to JSON and reloaded through a second code path.
- [x] Minimal physical case implemented as steady fully developed laminar
  axial flow in a concentric annulus.
- [x] Physical record written to JSON and reloaded through a second code path.
- [x] Analytical global targets saved: mean velocity, Reynolds number,
  pressure gradient, pressure drop.
- [x] Analytical local targets saved: sampled axial velocity profile,
  maximum velocity, inner-wall shear stress, outer-wall shear stress.
- [ ] Minimal dataset built.
- [ ] Tiny surrogate model trained.
- [ ] Inference tested.
- [ ] Minimal optimization loop.
- [ ] Full end-to-end integration check.

### Progress log

- [x] Repo created on GitHub (private), cloned locally to `~/work/sgk-mini/`.
- [x] PicoGK verified buildable on Fedora 44 / .NET 9 (outside this repo).
- [x] `.gitignore` and `README.md` bootstrapped.
- [x] First PicoGK project scaffolded (`src/SGK.Geometry`).
- [x] First voxel shape (hollow cylinder) generated and inspected in PicoGK
  viewer — native runtime built from source on Fedora 44, validated across
  6 executions (interactive + agent-invoked, including abrupt SIGINT
  termination). One intermittent crash during initial build session was
  root-caused via coredump analysis to a Mesa/Intel ARL driver race
  condition (`libgallium-26.1.5.so`), external to this codebase and not
  actionable here.
- [x] Hollow-cylinder voxel geometry serialized to `.vdb`, reloaded, and
  validated by voxel equality, identical volume, and identical bounding box.
- [x] Minimal feature record extracted from post-reload geometry, written to
  `output/hollow-cylinder.features.json`, reloaded through a second code path,
  and validated for schema identity plus minimal numeric sanity.
- [x] Minimal physical record extracted from the validated feature record and
  written to `output/hollow-cylinder.physical-case.json`.
- [x] Physical record reloaded through a second code path and validated for
  schema identity, geometric sanity, laminar-regime sanity, and positive
  pressure-drop results.
- [x] Analytical annulus benchmark extended with local validation targets:
  sampled axial velocity profile, maximum velocity location, and wall shear
  stress on both inner and outer walls.

### Current task boundaries

This checkpoint now validates the first complete geometry-to-physics mini-slice:

1. Generate hollow-cylinder voxel geometry.
2. Save geometry to `.vdb`.
3. Reload geometry from `.vdb`.
4. Extract minimal numeric features from the reloaded geometry.
5. Save the feature record to JSON.
6. Read the feature JSON back through a second code path.
7. Compute an analytical physical benchmark from the validated feature record.
8. Save the physical record to JSON.
9. Read the physical JSON back through a second code path.
10. Validate schema identity and minimal physical sanity.
11. Save analytical local targets for future CFD comparison.

This remains intentionally narrow. It still does not touch OpenFOAM execution,
PhysicsNeMo, FEM, or CEA.

### Physical case used now

The current physical benchmark is:

- Steady flow.
- Incompressible Newtonian fluid.
- Fully developed axial laminar flow.
- Concentric annular passage.
- Constant cross-section.
- No-slip walls.
- Entry and exit effects neglected.

The hollow-cylinder voxel geometry is interpreted as the solid wall of the flow
passage. The fluid domain is the concentric annular gap implied by the geometry,
not the solid voxel object itself.

### Why this case

This case is small, analytical, and honest. It consumes the feature record already
validated by the geometry pipeline and produces both global and local quantities
that are useful for future solver validation.

That makes it a good SGK-mini checkpoint: small code, explicit assumptions,
numerical output that can be saved, and a direct future path toward OpenFOAM
comparison.

### Next planned step

Use the current analytical annulus benchmark as ground truth for the first
OpenFOAM-oriented validation step. The next checkpoint should compare future CFD
results against:

- pressure gradient / pressure drop,
- sampled axial velocity profile,
- maximum velocity and its radial location,
- wall shear stress at inner and outer walls.

Native runtime build details remain archived separately in the SGK vault for
reproducibility on future machines/clones.
