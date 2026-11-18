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
