# Pipeline

The annulus dataset pipeline. It is deliberately small and case-first: the
annular case is an instance, not a framework.

## Files

- `annulus_case.py` — the annular case model: request, admissibility, geometry
  configuration, OpenFOAM case generation, reference run, dataset record.
- `sample_cases.py` — LHS design, feasibility filter, maximin selection.
- `run_pilot.py` — orchestration and the compact report table.
- `pilot-cases.json` — the committed design (seed, bounds, cases).
- `reports/` — compact, committed results; the data itself is elsewhere.

## Data layout

Generated data lives outside the repository, in `~/data/datasets/sgk-mini/`:

```
<case-id>/
  case-request.json          requested parameters
  geometry-config.json       exact config passed to SGK.Geometry
  log.geometry               geometry stage stdout/stderr
  geometry/
    <case-id>.vdb
    <case-id>.features.json
    <case-id>.physical-case.json
  openfoam/                  generated case, dictionaries, logs, fields
  log.reference              full run_annulus.sh output
  dataset-record.json        request, records, checks, hashes, provenance
```

`index.json` at the dataset root summarises every case that has a record.
A failed case keeps its record and whatever artifacts it produced.

## Run

```bash
dotnet build src/SGK.Geometry/ -c Debug
~/data/venvs/sgk-mini/bin/python pipeline/sample_cases.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py
~/data/venvs/sgk-mini/bin/python pipeline/run_pilot.py --only ann-XXXXXXXX
```

The pilot stops after the eight requested cases. Nothing trains a model and
nothing generates the full batch.

## What the pipeline does not decide

The mesher, the solver schemes and the physical model are the validated
reference configuration. `prepare_openfoam_case` copies the reference
dictionaries and changes only the case literals (radii, length, imposed mean
velocity, kinematic viscosity, radial cell count). Every literal is re-checked
against the physical record by `run_annulus.sh` before `blockMesh`.
