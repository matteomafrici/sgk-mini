# SGK Mini state and handoff

This note records the state after the verified annulus pilot at `4a4fe68`
and the subsequent review of the four-layer workflow. Use the SGK repository
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
- Each attempt has its own directory, diagnostics and artifact hashes. Failed
  attempts remain available. Voxel refinement has been tested manually on
  individual cases and is not automatic in the runner.
- The complete dataset, final training split, geometry-to-tensor converter,
  trained models, search policy and AI interface remain open. The CFD mesh is
  built from reconstructed dimensions. The mini has not verified general
  VDB-to-CFD meshing.
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

1. Freeze a versioned first batch manifest and the split policy before training.
   Twenty CFD cases is the proposed initial budget in the dataset plan.
   Treat it as a budget for a first learning curve. Group complete cases by
   normalized shape, using `Ri/Ro` for the concentric annulus. Keep resolutions
   and equivalent profiles together. Declare held-out shape groups and an
   edge test. Record whether the batch includes the existing pilot or starts
   a fresh design. Keep the diagnostic stress run separate from the split.
2. Run the declared CFD batch in a fresh dataset root. Start at 0.2 mm voxel
   size and try finer resolution only for cases that miss geometry checks.
   Preserve each attempt. Reuse an accepted field only when its case identity,
   solver configuration and artifact hashes match. Check the final index
   against the manifest, including rejected or missing cases.
3. Verify the converter on one accepted case. Derive geometry input from
   PicoGK, align the voxel and CFD coordinate systems, and test units, wall
   positions, positional sampling and numerical integration of the saved
   labels. OpenFOAM's periodic pressure field and the driving pressure
   gradient are distinct outputs. Save the converter configuration.
4. Train the simplest supervised controls and a small geometry-aware model.
   Check one-case reconstruction first, then held-out geometry, wall error,
   mass balance and the engineering quantities used by search.
5. Close the loop with a small L3 experiment and the structured L4 entry
   point. Inject a plausible surrogate error and confirm that reference
   rejection leads to another proposal or a clear stop. Record one
   independently reproducible end-to-end run before expanding the physics.

## Knowledge base updates

This is the project-local handoff. The solver evidence stays in
`pipeline/reports/`, the generated fields stay under
`~/data/datasets/sgk-mini/`, and the main SGK README remains the source for
the long-term scope and decisions on the first propulsion application.

## Open questions

- How many accepted CFD cases are needed for a useful learning curve after
  reserving whole geometry groups for validation and test?
- How much does CFD-to-tensor sampling change flow and wall metrics? What
  mesh sensitivity should be resolved before setting the L2 tolerance?
- Can learned search improve the quality of a verified candidate at fixed
  evaluation budget over simple search on this family?
- After the mini, which decision, physical regime and output justify the
  first operational SGK model? Which errors would change that decision?
