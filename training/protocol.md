# SGK Mini supervised Layer 2 protocol

The first experiment tests the data and inference path. It also establishes a
parameter-only comparator for spatial models. The 20 physical cases are a
small pilot, with 11 training, 4 validation, 3 test and 2 stress cases. Rows
within a case are quadrature samples. The physical case is the unit of
training aggregation, validation and testing.

## Stages

| Stage | Purpose | Promotion evidence |
|---|---|---|
| MLP smoke | Fit one training case. Use it again for the reconstruction diagnostic | Finite updates and all screening metrics pass on that case |
| MLP supervised | Establish a parameter baseline on all training cases | Review the fixed validation gates before opening held-out cases |
| FNO supervised | Exercise geometry on a regular grid and map its field back to the same native queries | First verify the grid-to-field transfer independently. Compare the same validation cases and metrics |
| GINO supervised | Exercise VDB surface samples, signed distances and arbitrary query locations | Start with one-case reconstruction. Keep the same splits, physical scales, and metrics as the baselines |
| Optional PINO comparison | Measure the effect of physics losses | Match the architecture, split, and compute budget to the supervised experiment. Check residuals against the exact solution before using them |
| Frozen model evaluation | Measure performance on unseen geometries and stress points | Lock model and selection decisions before evaluation. Report each case |

The MLP consumes the reconstructed radius ratio and the corrected radial
coordinate normalized across the gap. Operating conditions enter through
the stored mean velocity and viscous gradient scales. The case is steady,
fully developed and axisymmetric. This baseline learns the axial profile and
uses zero transverse components. It also learns a scalar driving gradient.
It uses a smooth zero-wall envelope. This hard boundary condition is separate
from the optional physics-residual loss. The periodic pressure is not used
as a driving-gradient label.

The field loss is a volume-weighted mean squared error normalized by mean
velocity. The gradient head predicts the log of the positive normalized
gradient. Each case counts once in checkpoint selection, regardless of its
mesh size. The combined selection loss is field loss plus 0.1 times squared
log-gradient error. The smoke reconstruction uses the same objective. The
training targets come from CFD. The analytical solution is an independent
evaluation reference.

## Screening gates for this pilot

All of these are strict relative limits and apply individually to each
validation case. They are experimental starting criteria for Layer 2. The
CFD dataset retains its own acceptance thresholds.

| Quantity | Limit | Reference |
|---|---:|---|
| Volume-weighted velocity relative L2 | 2% | CFD |
| Maximum velocity error in the first or last 10% of the gap | 3% of reference peak | CFD |
| Peak at the sampled cell locations | 2% | CFD |
| Flow integrated from the predicted field using cell volumes | 1% | Imposed flow |
| Driving gradient | 5% | CFD |

On each case the evaluator also reports model-to-analytical and
CFD-to-analytical field and gradient errors, evaluated at the same radii where
applicable. The analytical gradient and native CFD gradient are positive
magnitudes. A stage that misses its gate still publishes metrics and a
checkpoint for diagnosis. The held-out evaluation command refuses to open
test and stress cases unless the full supervised run passed its validation
gates. Test and stress results are separate from checkpoint selection.

Report elapsed wall time, device, seed, dataset digest, source revision,
per-case metrics, chosen checkpoint and applicable domain on every run.
Before extending beyond this family, judge whether error levels could change
a feasibility decision or swap candidate rankings.

## References for the experimental choices

- [GINO (NeurIPS 2023)](https://proceedings.neurips.cc/paper_files/paper/2023/file/70518ea42831f02afc3a2828993935ad-Paper-Conference.pdf)
  motivates geometry-to-query operators. The reported vehicle surface-pressure
  experiment leaves volume-velocity evaluation to our own tests.
- [PINO](https://authors.library.caltech.edu/records/06m4r-8jf10) motivates
  adding physics constraints in a measured comparison with supervised training.
- [AirfRANS (NeurIPS 2022)](https://proceedings.neurips.cc/paper_files/paper/2022/hash/94ab7b23a345f93333eac8748a66c763-Abstract-Datasets_and_Benchmarks.html)
  and [structured-shift experiments (TMLR 2026)](https://openreview.net/pdf/5f9a8276e0927f1e355598c2f3fbb0f21e74f0e5.pdf)
  motivate separate tests on withheld geometry or physical conditions.
- [NASA CFD verification guidance](https://www.grc.nasa.gov/www/wind/valid/tutorial/verassess.html)
  motivates keeping grid, iterative, conservation and benchmark checks
  separate from errors introduced by a learned model.
- [RIBBO (IJCAI 2025)](https://www.ijcai.org/proceedings/2025/994) motivates
  studying learned search separately from field prediction. [Constrained
  Bayesian optimization](https://proceedings.mlr.press/v32/gardner14.html)
  provides a comparator when evaluating a learned search policy.

## Controlled MLP follow-up

Retain the first outer-radius-scaled CFD baseline. For the scaling control,
train the same network on the same 11 CFD cases with the gap as the length
scale in the gradient target. Keep the 300 epochs, seed and gates fixed.

For the data-size experiment, use the gap scale throughout and use the same
3,300 optimizer updates with 300 validation observations. Compare 4, 7 and
11 evenly spread CFD training shapes. Separately compare 11 analytical
profiles at the CFD training ratios and 64 analytical profiles covering
more of the same permitted ratio range. The analytical generator excludes
all validation, test and stress bands. All comparisons score the same four
CFD validation cases. Neither comparison opens the final splits.

## Meridional FNO

The baseline uses the current axisymmetric wedge, not a 3D field extrapolated
around the circle. Use a 65 × 32 meridional grid in gap and axial coordinates,
the VDB distance interpolated at the meridional plane, and the radius ratio.
The native CFD field is mapped to and back from this grid as an independent
verification. In the radial direction the transfer uses the two known zero
wall values. In the axial direction it respects the periodic seam. Each
training and validation case must have transfer errors below 0.2% field,
0.3% wall and 0.1% integrated flow relative to the native data.

For supervised training, evaluate the predicted grid at the original cell
centres so the optimizer and the acceptance tests use the same native targets
and weights as the parameter MLP. Keep the zero-wall envelope. Predict the
positive gap-scaled driving gradient using the spatial mean of the separate
log-gradient output. Use three Fourier layers, width 16 and eight modes per
dimension. The first complete run uses 300 epochs and the existing seed and
validation gates. The reconstruction step and both training stages leave test
and stress cases closed.
