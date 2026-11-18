# SGK Mini training pipeline

Review the [protocol and screening gates](protocol.md) first. The executable
first stage is the parameter MLP. FNO, GINO and the optional physics-loss
comparison are separate milestones with the same evaluation contract.

Use the existing `sgk-neuralop` environment. The MLP uses two CPU threads by
default. The training data is read from the prepared, hashed batch index.

```bash
~/data/venvs/sgk-neuralop/bin/python training/train_annulus.py mlp-smoke
~/data/venvs/sgk-neuralop/bin/python training/train_annulus.py mlp
```

Run the smoke diagnostic first and inspect its result before starting the
full parameter baseline. The smoke result is a reconstruction of a training
case. The full MLP selects its checkpoint using only the four validation
cases. Both stages write a run receipt, event metrics, a log, a validation
report and a checkpoint to the dataset's `runs/` directory. The workbench
reads them at its normal refresh rate.

The held-out stage requires an explicitly selected qualified full run:

```bash
~/data/venvs/sgk-neuralop/bin/python training/train_annulus.py mlp-evaluate \
  --run ~/data/datasets/sgk-mini/annulus-v1/runs/<qualified-run-id>
```

This evaluates both the test and stress groups only after verifying the dataset
and checkpoint digests and the validation gate. It writes a separate
`held-out.json`. The CLI will not overwrite an existing held-out result.

CUDA can be selected with `--device cuda`. The program checks availability.
For the parameter MLP, CPU avoids small-dispatch accelerators' overhead.
Benchmark a short run before estimating the spatial models. Count time for
data mapping, training and inference separately.

## First measurements

The first one-case smoke experiment at `c6604f0` completed 300 epochs in
4.72 s of trainer wall time on CPU. It passed all screening gates on the
reconstructed training case, including 0.5653% field error versus CFD and
0.2183% integrated-flow error. Its receipt is in the dataset's
`runs/mlp-smoke-20261118T223048008723Z/` directory.

A separate 30-epoch timing run on all training and validation cases took
1.25 s of trainer wall time. It used a temporary run directory. The full
baseline still needs its own run and validation review. The test and
stress splits remained unopened in both experiments.

On the local RTX 5070 Ti Laptop GPU, a synthetic 48 × 64 FNO step took
about 0.0067 s and a synthetic 24 × 24 × 16 GINO step took about 1.86 s with
1,024 surface points, 1,300 queries and the pure PyTorch neighbour search.
These are forward/backward/optimizer timings for one example. They omit
conversion, validation, and any transfer or geometry caching work. They do
not qualify either spatial model. Benchmark actual case geometry, neighbour
coverage and memory before committing to a GINO training budget.

## First complete MLP baseline

Run `mlp-20261118T223725546780Z` at `0309079` used 11 training cases and
four validation cases. It completed 300 epochs in 5.72 s on CPU and selected
epoch 11. The screening gate failed. The table shows percentage errors
computed on the selected checkpoint.

| Validation case | Field | Wall | Sampled peak | Flow | Driving gradient |
|---|---:|---:|---:|---:|---:|
| ann-dce3a2fb | 2.184 | 2.513 | 0.501 | 0.975 | 3.365 |
| ann-96018040 | 2.411 | 2.744 | 0.730 | 1.182 | 7.624 |
| ann-4da45406 | 2.393 | 2.726 | 0.713 | 1.166 | 6.794 |
| ann-d80e8f87 | 2.699 | 3.031 | 1.013 | 1.436 | 21.167 |

The saved checkpoint reproduced all validation metrics on reload. The field
error between CFD and the analytical profile was about 0.0073% for these
cases. The model exhibits a systematic low-velocity region toward the inner
wall. All test and stress cases remain unopened.

A diagnostic using only training labels found that the gradient normalized
by `mu * Ubar / Ro^2` varied from 41.65 to 2043.46. Replacing outer radius by
gap in that scale gave a range of 11.888 to 11.999. Linear interpolation in
`Ri/Ro` of the gap-scaled training labels gave 0.0118%–0.0154% gradient error
on these validation samples. This diagnostic motivates a controlled scaling
comparison and says nothing about the velocity error or the stress split.
The original checkpoint and screening gates are retained.

## Resolved parameter baseline on validation

Run `mlp-20261118T224857780942Z` at `1c53d21` is the controlled comparison
with the first complete baseline. It retains the original CFD case order,
300 epochs, seed and loss, and changes the gradient scale to
`mu * Ubar / gap^2`. It selected epoch 297 and passes every fixed gate
on all four validation cases. Reloading the checkpoint reproduced the metrics.
The maximum flow error at each of the 300 epochs is identical in the two
controlled runs. The velocity and gradient heads have separate parameters.
The new gradient scale removed the bias in checkpoint selection toward epoch
11, where the velocity head had had fewer updates.

| Training labels and order | Maximum field error (%) | Maximum flow error (%) | Maximum gradient error (%) |
|---|---:|---:|---:|
| CFD 11, original scale and order | 2.699 | 1.436 | 21.167 |
| CFD 11, gap scale and original order | 0.149 | 0.024 | 0.191 |
| CFD 4, gap scale and ratio order | 0.140 | 0.013 | 0.574 |
| CFD 7, gap scale and ratio order | 0.127 | 0.024 | 0.414 |
| CFD 11, gap scale and ratio order | 0.131 | 0.018 | 0.420 |
| Analytical 11, gap scale and matched ratios | 0.106 | 0.014 | 0.438 |
| Analytical 64, gap scale and denser ratios | 0.142 | 0.065 | 0.084 |

All follow-up runs used 3,300 optimizer updates and 300 validation
observations. A single seed and four validation cases cannot establish a
learning curve for a wider distribution. Here, denser analytical coverage
improved gradient accuracy while velocity and flow error rose slightly.
No extra CFD labels are required to meet the current validation gates.
The recommended parameter comparator is the gap-scaled model trained on
all 11 CFD cases in original order:

```bash
~/data/venvs/sgk-neuralop/bin/python training/train_annulus.py mlp \
  --gradient-scale gap --updates-per-epoch 11
```

The gates and data splits did not change after the experiment. No
test or stress outputs were opened. Hold those splits for the planned frozen
comparison after the spatial baselines have been evaluated on validation.

## Meridional FNO

The FNO stage uses the same case split, query weights and acceptance
metrics as the MLP. It trains on the calibrated axial component in a
meridional representation of the periodic wedge.

```bash
~/data/venvs/sgk-neuralop/bin/python training/train_fno.py grid-check
~/data/venvs/sgk-neuralop/bin/python training/train_fno.py fno-smoke --device cuda
~/data/venvs/sgk-neuralop/bin/python training/train_fno.py fno --device cuda
```

The first command measures the grid transfer alone. Each training entry
point repeats the relevant transfer gate before updating weights. Only
training and validation cases are read by this CLI. Run receipts identify
the model, grid configuration and NeuralOperator version.
