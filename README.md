# SGK Mini

SGK Mini is the validation testbed for the Space Generative Kernel (SGK).
It builds a voxel model of a hollow cylinder with PicoGK, recovers the
dimensions of the annular flow passage, and compares a closed-form solution
for fully developed laminar flow with an OpenFOAM simulation. A batch of
these cases provides reference data for testing learned flow predictors.

The reference solver builds its mesh from the recovered annulus dimensions.
The pipeline also prepares voxel surface samples and signed distances for
geometry-aware models.

## Current status

- The reference case passed the analytical and CFD checks. All **20 CFD
  batch cases** were accepted and converted to model inputs.
- The MLP and meridional Fourier neural operator (FNO) passed all screening
  gates on the four validation cases. Their maximum field errors against
  CFD were **0.149%** and **0.067%**, respectively. The three test cases
  and two stress cases remain reserved for held-out evaluation.
- **Next:** verify GINO, the geometry-informed neural operator, on one
  real training case, from VDB surface samples to a reloaded checkpoint.
  A common held-out evaluator and the design search loop remain open.

See the [batch report](pipeline/reports/batch-v1.md),
[training results](training/README.md), and
[project handoff](docs/sgk-mini-status.md).

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

## Repository guide

| Path | Contents |
| --- | --- |
| [src/SGK.Geometry/](src/SGK.Geometry/) | C# geometry generation, voxel sampling, and the analytical flow model |
| [validation/](validation/README.md) | OpenFOAM case, reference records, and numerical checks |
| [pipeline/](pipeline/README.md) | Batch manifests, CFD orchestration, and conversion to model inputs |
| [training/](training/README.md) | MLP and FNO commands, validation protocol, and results |
| [workbench/](workbench/README.md) | Local read-only viewer for case geometry, checks, and runs |

Generated geometry and solver fields, prepared datasets, and model weights
are produced locally. The committed inputs and reports document how to
regenerate them.
