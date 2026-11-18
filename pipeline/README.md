# Pipeline

The annulus dataset pipeline. It is deliberately small and case-first: the
annular case is an instance, not a framework.

## Files

- `annulus_case.py` — the annular case model: request, admissibility, geometry
  configuration, OpenFOAM case generation, reference run, dataset record.
- `sample_cases.py` — complete Latin hypercube designs, screened for feasibility
  and selected by minimum pairwise distance.
- `run_pilot.py` — orchestration and the compact report table.
- `pilot-cases.json` — the historical eight-case design and its original results.
- `pilot-cases-lhs.json` — the follow-up design with eight points and one point
  per stratum in each dimension.
- `pilot-cases-lhs-refined.json` — the executed follow-up design. It preserves
  the same physical points and uses finer voxels for the two geometries that
  missed the volume tolerance at 0.2 mm.
- `reports/` — compact, committed results; the data itself is elsewhere.

## Data layout

Generated data lives outside the repository, in `~/data/datasets/sgk-mini/`:

```
<case-id>/attempts/<run-id>/
  case-request.json          requested parameters
  geometry-config.json       exact config passed to SGK.Geometry
  log.geometry               geometry stage stdout/stderr
  geometry/
    <case-id>.vdb
    <case-id>.features.json
    <case-id>.physical-case.json
  openfoam/                  generated case, dictionaries, logs, fields
  log.reference              full run_annulus.sh output
  source.patch               tracked source changes against the recorded commit
  dataset-record.json        request, records, checks, hashes, provenance
```

`index.json` at the dataset root summarises the latest published attempt per case
and links all previous records, including records from the original layout.
Each attempt keeps its artifacts and failures. The record includes an assembly
hash and the source patch captures tracked edits for runs with local changes.

## Run

```bash
dotnet build src/SGK.Geometry/ -c Debug
~/data/venvs/sgk-mini/bin/python pipeline/sample_cases.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py --only ann-XXXXXXXX
```

Use `--cases pipeline/pilot-cases-lhs-refined.json` to reproduce the executed
follow-up design.
Use `--reports` to select a distinct report directory when comparing designs.

The pilot stops after the eight requested cases. Nothing trains a model and
nothing generates the full batch.

## What the pipeline does not decide

The mesher, the solver schemes and the physical model are the validated
reference configuration. `prepare_openfoam_case` copies the reference
dictionaries and sets the case literals (radii, length, imposed mean velocity,
kinematic viscosity, and axial and radial cell counts). The number of axial
cells depends on length and radial pitch. A short, wide-gap annulus can have
eight axial cells, while a long or narrow-gap annulus can need more. The runner
checks the physical inputs before `blockMesh` and requires `checkMesh` to
report `Mesh OK.` before starting the solver.

## Initial CFD batch

`batch-cases-v1.json` freezes 20 new physical points from the seeded Latin
hypercube. It reserves shape bands for validation, test and edge evaluation
before any solver run. Voxel retries inherit the physical point and split.

```bash
~/data/venvs/sgk-mini/bin/python pipeline/run_batch.py --jobs 8
```

The default output root is `~/data/datasets/sgk-mini/annulus-v1/`.
The batch runner tests geometry before spending a solver run, follows the
recorded voxel schedule, and publishes an index after each completed physical
point. Re-running the command resumes the same manifest and verifies hashes
before reusing a published attempt. A solver rejection is retained for
diagnosis. Only index entries with status `ok` are eligible as labels.

If the original run needs the recorded edge-case recovery, resume it with
`--recovery pipeline/batch-recovery-v1.json`. The base manifest and existing
attempts stay in the dataset root. The recovery file records why a finer
geometry or a repeated reference run was requested. A later resume reuses the
same recovery plan from the dataset root.

## One-case conversion probe

Build the geometry program, then convert an accepted training case:

```bash
dotnet build src/SGK.Geometry/ -c Debug
~/data/venvs/sgk-mini/bin/python pipeline/convert_annulus.py \
  --root ~/data/datasets/sgk-mini/annulus-v1 \
  --case ann-7939f294 \
  --out ~/data/datasets/sgk-mini/annulus-v1/converter-reproduction
```

PicoGK reloads the accepted VDB and extracts surface vertices and a signed
distance sampled on nearby voxels. The distance is in millimetres and clipped
to one voxel. The converter exports SI arrays with the PicoGK axis convention,
native OpenFOAM cell weights, and separate periodic pressure and applied
pressure-gradient targets. Negative signed distance denotes VDB material.
The annulus benchmark uses that geometry's extent for its fluid domain.

This is a conversion probe. Its output grid and point density have not been
chosen for training. The native CFD field is kept at its original centres,
with axis remapping and units checked before comparing the saved array's
flow to the validated reference integral.
