# SGK Workbench

The workbench is a local, read-only viewer for SGK Mini development artifacts.
It runs with Python and NumPy.

A fresh clone needs a generated dataset. Follow the
[CFD batch instructions](../pipeline/README.md#initial-cfd-batch) to produce
the dataset's `index.json` and case records. Follow the
[conversion instructions](../pipeline/README.md#prepared-model-inputs) to
enable the 3D geometry and field views. Run receipts are optional.

From the repository root, use a Python environment with NumPy installed:

```bash
python3 workbench/serve.py --dataset /path/to/annulus-v1
```

Replace the example path with the directory containing `index.json`.
If you used the default batch location, `~/data/datasets/sgk-mini/annulus-v1/`,
you can omit `--dataset`.

Open the URL printed in the terminal on the same computer. The default is
[127.0.0.1:8765](http://127.0.0.1:8765/). Use `--port` if that port is in use
and `--runs` if your training receipts are outside the dataset's `runs/`
subdirectory. Stop the server with Ctrl+C.

## What the workbench reads

- Case status, filters and aggregate metrics come from the dataset index and
  selected CFD records. An unpublished attempt can show its current artifact
  stage and available solver log. Stage reflects available evidence.
- The 3D viewer draws a bounded sample of the VDB surface and native CFD
  points in the PicoGK frame. The velocity tab compares the central axial
  station with the analytical profile. The SDF tab shows the sign and distance
  at the middle prepared grid slice. Click a field sample for its value.
- The inspector links the selected case, reference checks and historical
  attempts. The log viewer shows bounded tails of existing logs.
- Source history shows recent Git commits with a bounded read-only view of
  each diff. It can be used alongside the normal editor and terminal.

## Run receipts for training

The run producer owns its outputs. The browser reads them on refresh. Under
the configured run directory, create one subdirectory per run:

```text
runs/<run-id>/run.json
runs/<run-id>/run.log
runs/<run-id>/metrics.jsonl
```

`run.json` is an object with string fields such as `model`, `status`, `commit`,
`command`, `started_at` and `updated_at`. Replace it atomically when publishing a
new state. Use ISO-8601 timestamps. Logs are optional plain text. Append one
object per line to `metrics.jsonl`, with numeric `step`, `train_loss` and
`validation_loss`. The viewer skips incomplete metric lines and only plots
training and validation losses. The single-case diagnostic uses the
comparison label Reconstruction. See the [trainer](../training/README.md).

The same receipt and log format can describe a non-training run. Native field
views currently read SGK Mini's annulus assets and OpenFOAM outputs. Add
solver-specific readers and prediction comparisons when their producers
publish actual fields. Keep final test and stress scores with explicit
evaluation artifacts for a frozen checkpoint.
