# SGK Mini

[SGK (Space Generative Kernel)](https://github.com/matteomafrici/sgk) is a
project for propulsion analysis and design. In the proposed workflow, a
physical case and a set of design parameters define the geometry. Trained
models evaluate candidates as the search decides which change to try next.
Reference solvers supply training data and verify selected designs.

SGK Mini is a testbed for that workflow. The aim is to exercise all four
layers on a controlled problem, from an explicit design request to a
reference-checked result. Keeping the physics simple makes it possible to
trace a wrong design decision back to the geometry, the data, the predictor,
or the search. In a propulsion application, the physics, reference solver,
and model outputs will depend on the conditions and on the design decision
being made.

## Physical case

The benchmark is steady, fully developed laminar water flow through a
concentric annulus, the gap between two cylinders. A case specifies the radii,
length, fluid properties, and flow rate. For this problem the velocity
profile and the pressure gradient needed to drive the flow are known
analytically.

PicoGK generates the voxel geometry. The volume and bounding box give the
dimensions of an equivalent annulus. OpenFOAM builds a periodic wedge mesh
from those dimensions. For the model, we sample the VDB surface and signed
distances and put them in the same coordinate frame as the CFD cell centres.
We use the analytical solution to check the CFD and compare transferred
fields with the original CFD samples to check the mapping onto model grids.

The annulus gives the models a controlled test. Its normalized velocity
profile depends on one shape parameter, the ratio of the inner and outer
radii. We can test the data and inference pipeline on this family. Measuring
the benefit of a model that reads geometry directly requires more varied shapes.

## How the SGK layers map to the Mini

| SGK layer | Role in SGK | Experiment in SGK Mini |
| --- | --- | --- |
| 1. Preliminary physics and geometry | Resolve the case inputs and generate geometry deterministically. | Build a voxel annulus from explicit dimensions, recover its dimensions, and compute the analytical flow for the given conditions. |
| 2. Fast physical evaluation | Use a trained model to predict fields and engineering quantities from geometry and operating conditions. | Use checked CFD fields as training targets. Compare a parameter model, a grid model, and a geometry-informed model on axial velocity and driving pressure gradient. Integrate the predicted velocity to check the flow rate. |
| 3. Design search | Propose the next change from the objectives, constraints, remaining budget, and previous evaluations. | Test a learned policy that sends new annulus dimensions back to Layer 1. Compare the designs it finds with those from a parameter sweep at equal budget. |
| 4. User interface | Turn a user request into explicit inputs and expose the case, decisions, and results. | Run the same design case from a structured request and its equivalent user-facing input. Keep units, assumptions, candidate history, and verification results visible. |

The reference and design paths have different jobs. In the reference path,
OpenFOAM provides training targets after checks on the mesh, conservation,
convergence, and agreement with the analytical solution. In the design
path, the search proposes parameters, Layer 1 rebuilds the geometry, and
Layer 2 evaluates the new case. Selected candidates go back to OpenFOAM
for verification. If the solver rejects a candidate, the search can use that
result to try again within the remaining budget or report why it stopped.

## Current status

The voxel, analytical, and OpenFOAM checks pass on the reference case.
All **20 CFD cases** in the first batch passed the acceptance checks and were
converted to model inputs. The split is 11 training, 4 validation, 3 test,
and 2 stress cases. The workbench is read-only. The design search and the
interface for running a design request are still to be built.

### Training results

The multilayer perceptron (MLP) uses the reconstructed radius ratio and a
normalized radial coordinate. The Fourier neural operator (FNO) adds a
VDB-derived signed distance field on a regular radial and axial grid. Both
trained for 300 epochs on the same 11 cases and passed the thresholds on
all four validation cases. The test and stress splits remain reserved for
final evaluation.

| Metric | Reference | MLP | FNO |
| --- | --- | ---: | ---: |
| Velocity field error | OpenFOAM | 0.149% | 0.067% |
| Near-wall velocity error | OpenFOAM | 0.233% | 0.192% |
| Sampled peak velocity error | OpenFOAM | 0.153% | 0.077% |
| Integrated flow rate error | Imposed flow rate | 0.024% | 0.018% |
| Driving pressure gradient error | OpenFOAM | 0.191% | 0.040% |
| Training time | | 3.48 s (CPU) | 36.40 s (GPU) |

Errors are the largest observed across the four validation cases. The
[training report](training/README.md) gives the thresholds, run settings,
and checks against the analytical solution. The
[batch report](pipeline/reports/batch-v1.md) describes the dataset and its
acceptance checks.

### What remains

1. **Close the geometry-to-model path on one case.** Feed VDB surface samples
   and signed distances to GINO, the geometry-informed neural operator.
   Check coverage from surface to grid and from grid to CFD sample points,
   especially near the walls. Train on that case, reload the checkpoint,
   and compare the field and engineering quantities with both references.
2. **Evaluate the predictors on reserved cases.** Train and select GINO on
   the existing training and validation splits. Freeze the MLP, FNO, and GINO
   checkpoints, then run the same evaluator on the test and stress splits.
   A comparison with physics residuals can follow using the same model,
   splits, and training budget.
3. **Test design search.** Compare a learned proposal policy with a parameter
   sweep at equal evaluation budget. Start with analytical feedback, then
   repeat with a frozen predictor. Measure the quality of the best
   reference-verified candidate, the number of reference calls, and how the
   search handles a prediction that the solver rejects. Compare the cost of
   predictor-driven search with direct reference evaluation at comparable
   design quality. Record data preparation and training costs separately.
4. **Run the full design loop from a user request.** Check that the request
   leads to the same case and results as a hand-written configuration. Save
   the inputs, candidate history, and OpenFOAM verification so another
   reader can reproduce the run.

The [project handoff](docs/sgk-mini-status.md#next-steps) records the
implementation checks for each stage.

## Quick start

From the repository root, with the **.NET 9 SDK** and **Python 3** installed,
follow the [Linux PicoGK setup](validation/README.md#linux-picogk-setup),
then build and compare the generated analytical records with the committed
reference records:

```bash
python3 scripts/check_analytic.py
```

The geometry step opens the PicoGK viewer and closes it when the task ends.
It writes the VDB, extracted geometry features, and analytical flow record to
`output/`. To supply different case parameters, use the
[geometry command options](validation/README.md#geometry-command-options).

To include the CFD comparison, install OpenFOAM v2606, create a Python
environment for NumPy and Matplotlib, and point to OpenFOAM's environment
script:

```bash
python3 -m venv "$HOME/data/venvs/sgk-mini"
"$HOME/data/venvs/sgk-mini/bin/python" -m pip install numpy matplotlib
FOAM_BASHRC=/path/to/OpenFOAM-v2606/etc/bashrc \
  python3 scripts/check_analytic.py --with-cfd
```

NumPy is used by the numerical checks. Matplotlib lets the CFD runner
regenerate the figures. See the [validation guide](validation/README.md)
for the individual commands and environment overrides.

## Reference benchmark

Water flows through a concentric annulus with nominal radii of 8 and 10 mm,
a length of 50 mm, and a prescribed flow rate of 1 mL/s (Re ≈ 35).
The geometry uses 0.2 mm voxels. The OpenFOAM case uses a 2° periodic wedge
with **58 axial × 100 radial × 1 tangential cell**.

![Radial velocity profile comparing OpenFOAM and the analytical solution](validation/figures/01_velocity_profile.png)

In the reference run, the mean and maximum profile errors relative to the
analytical peak speed were **0.0046%** and **0.0071%**. The flow-rate error
was **0.0203%**, consistent with the measured area deficit of the finite
wedge. See the [full metrics, assumptions, and figures](validation/README.md#cfd-cross-check-openfoam).

## Workbench

The [workbench](workbench/README.md) shows the geometry, CFD samples, case
checks and training runs.

![SGK Workbench showing the 20-case batch and an annulus with its CFD samples](workbench/figures/overview.png)

## Repository guide

| Path | Contents |
| --- | --- |
| [src/SGK.Geometry/](src/SGK.Geometry/) | C# geometry generation, voxel sampling, and the analytical flow model |
| [validation/](validation/README.md) | OpenFOAM case, reference records, and numerical checks |
| [pipeline/](pipeline/README.md) | Batch manifests, CFD orchestration, and conversion to model inputs |
| [training/](training/README.md) | MLP and FNO commands, validation protocol, and results |

Generated geometry and solver fields, prepared datasets, and model weights
are produced locally. The committed inputs and reports document how to
regenerate them.
