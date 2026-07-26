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
3. A minimal physical case (simplified calculation, possibly CFD/FEM later).
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
- PicoGK 2.2.0 (referenced locally from `~/work/leap71-inspect/PicoGK` during
  development, for source-level learning).

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
└── src/
    └── SGK.Geometry/
        └── SGK.Geometry.csproj
```

This structure is intentionally minimal. It will grow only as validation goals are
checked off — not in anticipation of future needs.

---

## Current status

**Last updated:** 2026-07-27

### Validation checklist

- [ ] Repo builds and runs from a clean clone.
- [ ] C# + PicoGK integration works (voxel geometry generated and saved).
- [ ] A minimal physical case can be represented (starting: hollow cylinder).
- [ ] Geometry data can be serialized and reused downstream.
- [ ] Feature extraction from geometry.
- [ ] Minimal dataset built.
- [ ] Tiny surrogate model trained.
- [ ] Inference tested.
- [ ] Minimal optimization loop.
- [ ] Full end-to-end integration check.

### Progress log

- [x] Repo created on GitHub (private), cloned locally to `~/work/sgk-mini/`.
- [x] PicoGK verified buildable on Fedora 44 / .NET 9 (outside this repo).
- [x] `.gitignore` and `README.md` bootstrapped.
- [ ] First PicoGK project scaffolded.
- [ ] First voxel shape (hollow cylinder) generated and inspected in PicoGK viewer.

### Current task boundaries

This session (bootstrap task) does not touch OpenFOAM, PhysicsNeMo, FEM, or CEA —
those belong to later steps of the pipeline above (steps 3-6), not because they are
excluded from SGK Mini, but because this task's scope is narrower (Layer 1 embryo
only).

### Next planned step

Scaffold `src/SGK.Geometry` as a .NET console project referencing PicoGK locally,
then write the first `Program.cs` (Library.Go + hollow cylinder) line by line.
