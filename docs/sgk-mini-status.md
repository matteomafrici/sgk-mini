# SGK Mini state and handoff

This note records the verified annulus pilot at `4a4fe68`, the first CFD
batch and the subsequent review of the four-layer workflow. Use the SGK repository
README (locally `/mnt/n/sgk/README.md`) as the source for the wider project.
Use this note to resume the mini.

## Current state

- D0 passes on the 2° periodic wedge. The strict eight-point Latin hypercube
  passed end to end. Two geometries needed 0.15 mm voxels. A separate stress
  case passed at reconstructed Re = 1989.7. These are numerical verification
  results for the tested configurations.
- OpenFOAM uses bounded `linearUpwind` and a case-dependent axial cell count.
  The runner requires `Mesh OK.` before solving. The acceptance checks require
  both native and saved-field flow errors below 0.05% and pressure-gradient
  error below 0.5%, along with the other checks in the protocol.
- The first CFD batch is complete. Its frozen design has 20 physical points:
  11 accepted for training, 4 for validation, 3 for test and 2 for edge
  evaluation. The narrow-gap edge point passed at 0.09 mm. Its failed attempts,
  including the native runtime crash at 0.05 mm, remain indexed.
  The batch runner applies a declared voxel recovery schedule and validates
  geometry before starting OpenFOAM.
- All 20 cases have converted VDB surface and signed-distance inputs, native
  CFD targets and weights in the PicoGK frame, and recorded physical scales.
  The model-input index is under
  `~/data/datasets/sgk-mini/annulus-v1/model-inputs-v1/`. The audit matched
  case identity and split, verified hashes and normalization round trips,
  and reproduced saved-field flow on every case. Training, search and the
  AI interface remain open. CFD still uses reconstructed annulus dimensions.
- The first [Layer 2 diagnostic](../training/README.md) passed. The parameter
  MLP reconstructed one training case in 4.72 s on CPU (300 epochs).
  Its field error against CFD was 0.5653% and its integrated-flow error was
  0.2183%. The subsequent supervised baseline used 11 train and 4 validation
  cases. Its selected checkpoint missed the screening gate, with worst
  field, flow and gradient errors of 2.699%, 1.436% and 21.167%.
  Test and edge remain unopened. The [baseline report](../training/README.md#first-complete-mlp-baseline)
  records an independent diagnostic of the gradient scaling.
- The controlled gap-scaling follow-up passed every validation gate with the
  same 11 CFD training cases. Peak validation errors were 0.149% on the
  field, 0.024% on flow and 0.191% on gradient. The CFD/analytical data-size
  comparison found no need for more CFD labels to meet the current gates.
  Keep this checkpoint as the parameter baseline. The meridional FNO also
  passed all validation gates after independently passing the grid-transfer
  check. Its maximum field, flow and gradient errors were 0.0673%, 0.0182%
  and 0.0405%. The [FNO results](../training/README.md#meridional-fno-results)
  record the checkpoint and timing. Test and stress remain unopened.
  GINO is the next Layer 2 comparator.
- The [read-only workbench](../workbench/README.md) displays the actual
  dataset, geometry, reference checks, attempt logs and Git diffs. Its run
  receipt format can display trainer logs and metrics when they are published.
- PhysicsNeMo 2.2.2 passed a synthetic FNO forward and backward CUDA check
  in the separate `sgk-pnm` environment. The recorded Mini baselines use
  PyTorch and NeuralOperator in `sgk-neuralop`.
- See the [batch report](../pipeline/reports/batch-v1.md) for the outcome,
  evidence and data paths.
- The eight executed inputs are in
  [pilot-cases-lhs-refined.json](../pipeline/pilot-cases-lhs-refined.json).
  Reproduction commands and evidence locations are in the
  [Reynolds readiness report](../pipeline/reports/reynolds-readiness.md).

## Decisions made

SGK Mini should exercise SGK's whole design loop on one simple physical case.
Its closing demonstration starts from an explicit user request and produces
a reference-checked design with a traceable history.

| Layer | Mini responsibility | Evidence required |
|---|---|---|
| 1 · Deterministic design | Turn explicit parameters into an annulus with PicoGK | Reproducible geometry, admissibility checks and clear rejection reasons |
| 2 · Physical evaluation | Predict the velocity field and engineering quantities from geometry and conditions | Held-out shape groups, analytical and CFD checks, wall behavior, integrated flow and driving gradient |
| 3 · Learned search | Propose the next geometry from objectives, constraints, budget and previous evaluations | Compare a learned policy with a simple sweep and, if useful, constrained Bayesian optimization at equal budget. Test on withheld design requests |
| 4 · AI interface | Convert user intent to structured inputs and report results | Equivalent execution to a manual request. Ambiguity, units, limits and verification status remain visible |

GINO is a candidate to exercise geometry-aware inference. A parameter model
and a fixed-grid model are diagnostic baselines. Add physics losses as a
controlled comparison with supervised training on matched splits and budgets.
Keep the case records independent of those model choices.

The optimizer learns which design to try. The predictor learns how a design
behaves. Test the optimizer first with analytical feedback and then with
frozen learned feedback. This exposes errors in the search strategy and
errors that arise when it acts on imperfect predictions. Compare the best
reference-confirmed design, failed feasibility claims and reference run count.
Record dataset and training cost separately from the cost of later searches.

Facility conditions belong to the physical case. Sensor response maps fields
to observations. The mini can test a virtual measurement on a known field.
Validation of a real facility or sensor calls for independent measurements
and a stated calibration and uncertainty model.

## Next steps

1. Build the first GINO input adapter on one training case. Fix deterministic
   VDB surface sampling, coordinates, normalization and grid resolution.
   Verify the encoder and decoder neighbourhood coverage, especially at
   native CFD queries near the walls. Measure graph construction time,
   update time and peak memory. If caching the neighbourhoods, test cached
   and uncached equality on the same inputs.
2. Finish one-case reconstruction with the existing field, wall, peak, flow
   and driving-gradient gates. Publish a workbench receipt, the checkpoint
   and a replay with the same input transforms. Produce a profile comparison
   against native CFD and the analytical solution. If a gate fails, record
   the failure and resolve its cause before scaling the run.
3. Compare GINO on the 11 training and four validation cases with the MLP and
   FNO. Complete a common evaluation entry point for the three frozen
   checkpoints before opening the test and stress splits. Keep the optional
   physics-loss comparison separate from architecture and data changes.
4. Close the loop with a small L3 experiment and the structured L4 entry
   point. Inject a plausible surrogate error and confirm that reference
   rejection leads to another proposal or a clear stop. Record one
   independently reproducible end-to-end run before expanding the physics.

## Knowledge base updates

This is the project-local handoff. The solver evidence stays in
`pipeline/reports/`, the generated fields stay under
`~/data/datasets/sgk-mini/`, and the main SGK README remains the source for
the long-term scope and decisions on the first propulsion application.
See the [environment and visualization notes](sgk-environment-notes.md)
for the four reusable resource groups, the roles of the candidate NVIDIA
tools, and a bounded first facility experiment.

## Open questions

- How many accepted CFD cases are needed for a useful learning curve after
  reserving whole geometry groups for validation and test?
- How much does CFD-to-tensor sampling change flow and wall metrics? What
  mesh sensitivity should be resolved before setting the L2 tolerance?
- Can learned search improve the quality of a verified candidate at fixed
  evaluation budget over simple search on this family?
- After the mini, which decision, physical regime and output justify the
  first operational SGK model? Which errors would change that decision?
