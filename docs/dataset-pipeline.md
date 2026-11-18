# Dataset generation pipeline

Scope: producing the dataset only. No training, no model, no search. Those come
after, and they consume what this pipeline writes.

The pipeline is written to be **independent of the physical case**. The annular
case is the first instance, not the definition. Everything that is specific to
the annulus lives in the case definition, never in the machinery.

## What the first dataset can and cannot teach

For steady, fully developed, laminar flow in a concentric annulus, the normalised
velocity profile `u(r)/U` depends on the radius ratio `Ri/Ro` alone, and the
pressure gradient is that profile times a scale. The family of fields has **one
shape parameter**.

Consequence: a dataset of concentric annuli proves the machinery and fixes the
metric baseline. It cannot show that a geometry-aware model learns geometry,
because there is almost no geometry to learn. That is expected and stated up
front; the eccentric annulus is the first family with real shape variation, and
it reuses the same pipeline unchanged.

## Pieces

Each piece has an input, an output and an acceptance criterion. A piece that
cannot fail is not a piece, it is decoration.

### D0 — Repair the reference case (decision, before any label exists)

The current mesh spans the wedge in three cells of 10°, so its cross-section is a
polygon with **0.507 % less flow area** than the annulus. That bias goes straight
into every label.

| Option | Bias in labels | Cost |
|---|---|---|
| keep 3 cells | −0.51 % area | 0 |
| 6 angular cells | −0.13 % area | 2× cells |
| 2D axisymmetric `wedge`, 1 cell | none | **⅓ of the cells** |

Recommendation: the axisymmetric wedge. It is both more accurate and cheaper,
because the problem is axisymmetric by construction and the third dimension is
pure overhead.

*Acceptance:* flow-rate error < 0.05 %, pressure-gradient error < 0.5 %.

### D1 — Case definition and sampling

- Parameters: `Ro`, `t = Ro − Ri` (the gap, which is what manufacturing
  constrains), `L`, `Q`.
- Bounds must respect two physical limits, not aesthetics:
  - `t ≥ 0.6 mm`, i.e. three voxels at 0.2 mm. Below that the geometry is a
    quantisation artefact.
  - `Re < 2000`, otherwise the laminar reference model is outside its domain.
    Note that `Re = 2ρQ / (πμ(Ro+Ri))`, so the limit constrains `Q` against
    `Ro+Ri`, not against the gap.
- Sampling: Latin hypercube, fixed seed, no duplicate or near-duplicate points.
- Splits by **group**, not by sample: cases with close parameters must not be
  split across train and test, or generalisation is memorisation.
- Output: `dataset/cases.json`, small and versioned, holding every parameter,
  the seed, the split and the case id.

Proposed bounds for v0, chosen against the two limits rather than by taste:

| Parameter | Range | Reason |
|---|---|---|
| `Ro` | 6 – 20 mm | keeps the part small enough for fast meshing |
| `t = Ro − Ri` | 0.6 – 6 mm | lower bound is three voxels at 0.2 mm |
| `L` | 10 – 60 mm | the cyclic case does not depend on length, so this only exercises the geometry stage |
| `Q` | 1e-6 – 3e-5 m³/s | gives `Re` between about 16 and 1100 across these radii, comfortably laminar |

`Q` is the one to check per case: `Re = 2ρQ / (πμ(Ro+Ri))`, so a large `Q` with
small radii is the dangerous corner.

*Acceptance:* every case satisfies both limits; the seed reproduces the file
byte-for-byte; no case in test has a neighbour within a declared distance in
train.

### D2 — Geometry stage per case

For each case: run the C# stage with `--config` at the declared voxel size, and
keep the feature record, the physical record and the VDB in the case directory.

*Acceptance:* reconstructed radii within 10 µm of the nominal ones; volume error
below 0.1 %; any case outside that is not silently accepted.

### D3 — Reference stage per case

Build the mesh **from the reconstructed radii in the record**, run the solver,
extract the field, keep the log.

*Acceptance:* residuals reached; mass balance closed; the radii guard in
`validate_annulus.py` passes; solver pressure gradient within the tolerance of
the analytical value. A run that diverges is a failure of the case, not of the
dataset, and is recorded as such.

### D4 — Record assembly

One record per case: case identity, geometry identity, reference-run identity,
diagnostics, integrated quantities, path to the field. Versioned schema.

*Acceptance:* every case in `cases.json` has either a complete record or an
explicit failure reason. No case may be silently missing — a missing case that
looks like a short dataset is the most expensive bug in this pipeline.

### D5 — Quality gate

Two independent checks on every label, because they fail in different ways:

1. **Against the analytical solution.** Every case has one, so a label that
   disagrees beyond the known mesh bias is wrong, and the pipeline is broken —
   not the physics.
2. **Mass balance from the saved field.** The integral of the stored velocity
   must equal the imposed flow rate. A field can match a profile and still fail
   this.

Plus an outlier rule: a case whose error is far from the median error of the
batch is inspected, not deleted.

*Acceptance:* a table with every case and its pass/fail per criterion, committed
with the dataset index. Failures stay visible.

### D6 — Dataset packaging

- `dataset/index.json`: case ids, splits, paths, schema version, seed, and the
  checksum of every file it references.
- Data on disk, outside the repository: `~/data/datasets/sgk-mini/`.
- The repository holds the generator, the index and the reports — not the data.

*Acceptance:* deleting the data and re-running the pipeline from the index
reproduces it.

### D7 — Geometry to model input (last piece, still part of the dataset)

Convert each case into what the model consumes: surface samples and a signed
distance field at a declared resolution, in a declared frame, with the
normalisation parameters saved alongside.

Precomputed rather than on the fly: deterministic, faster to train, and it makes
the converter itself testable.

*Acceptance:* round-trip check per case; identical converter used at inference;
a shape described twice gives the same tensors.

## Order of work, and why

1. **D0** — because every label would otherwise carry a known bias.
2. **D1 + D2 + D3** on **8 pilot cases** — the smallest number that exercises
   more than one parameter combination and still fits in one sitting.
3. Inspect the 8. If they are sane, run the rest.
4. **D4 + D5** — records and gates, applied to the whole batch.
5. **D6 + D7** — packaging and model input.

The pilot is not a formality: it is where a generator bug shows up as eight
wrong cases instead of fifty-eight.

## Failure policy

- A failed case stays in the index with its reason. Nothing is deleted.
- Labels are used only after D5 passes for that case.
- A systematic failure across the batch stops the run; a single failure does not.

## Decisions still open

| Decision | Needed before | Default if nobody decides |
|---|---|---|
| D0: which mesh | first label | 2D axisymmetric wedge |
| Number of cases | D1 | 20, not 58: the concentric family has one shape parameter, so more cases add little |
| `Ro`, `L` ranges | D1 | the table above, checked against the two limits |
| Storage layout | D6 | one directory per case, flat files |
