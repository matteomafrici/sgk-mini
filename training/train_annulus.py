#!/usr/bin/env python3
"""Train and verify the parameter-only baseline on the frozen annulus split."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import torch
from torch import nn

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / name) for name in ("pipeline", "validation")]
from annulus_case import DATASET_ROOT, sha256, write_json
from validate_annulus import U_analytical

DEFAULT = Path(DATASET_ROOT) / "annulus-v1"
LIMITS = {
    "field_cfd_pct": 2.0, "wall_cfd_pct": 3.0, "peak_cfd_pct": 2.0,
    "flow_pct": 1.0, "gradient_cfd_pct": 5.0,
}


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked_path(root, relative, expected):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or sha256(path) != expected:
        raise ValueError(f"dataset artifact failed integrity check: {relative}")
    return path


@dataclass
class Case:
    id: str
    split: str
    inputs: torch.Tensor
    velocity: torch.Tensor
    weights: torch.Tensor
    log_gradient: torch.Tensor
    analytical_velocity: np.ndarray
    physical_volumes: np.ndarray
    flow_factor: float
    imposed_flow: float
    gradient_scale: float
    analytical_gradient: float


class AnnulusData:
    def __init__(self, dataset, device, gradient_scale="outer-radius"):
        self.root = dataset.resolve()
        self.inputs = self.root / "model-inputs-v1"
        index = read(self.inputs / "index.json")
        checked_path(self.root, "index.json", index["source_index_sha256"])
        self.digest = sha256(self.inputs / "index.json")
        self.rows = index["cases"]
        source_index = read(self.root / "index.json")
        source = {row["physical_case_id"]: row for row in source_index["cases"]}
        self.split_bands = read(checked_path(
            self.root, "manifest.json", source_index["manifest_sha256"]
        ))["split_bands"]
        if (len(self.rows) != len(source)
                or {row["case_id"]: row["split"] for row in self.rows}
                != {key: row["split"] for key, row in source.items() if row["status"] == "ok"}):
            raise ValueError("prepared and reference splits or case IDs differ")
        self.device = device
        self.gradient_scale = gradient_scale

    def tensor(self, value):
        return torch.as_tensor(value, device=self.device, dtype=torch.float32)

    def gradient_unit(self, outer_scale, ratio):
        return outer_scale / (1 - ratio)**2 if self.gradient_scale == "gap" else outer_scale

    def cases(self, splits, case_id=None):
        rows = [row for row in self.rows if row["split"] in splits
                and (case_id is None or case_id == row["case_id"])]
        if not rows:
            raise ValueError("no cases match the requested split")
        return [self.load_case(row) for row in rows]

    def load_case(self, row):
        metadata = read(checked_path(self.inputs, row["metadata"], row["metadata_sha256"]))
        record = read(checked_path(self.root, metadata["source_record"],
                                   metadata["source_record_sha256"]))
        if metadata["case_id"] != row["case_id"] or metadata["split"] != row["split"]:
            raise ValueError("case metadata does not match the frozen split")
        physical = record["geometry"]["physical"]
        mesh = record["reference"]["report"]["mesh"]
        scale = metadata["normalization"]
        ri = physical["InnerRadiusMm"] * .001
        ro = physical["OuterRadiusMm"] * .001
        with np.load(checked_path(self.inputs, row["arrays"], row["arrays_sha256"]), allow_pickle=False) as data:
            radius = np.linalg.norm(data["query_xyz_m"][:, :2], axis=1)
            radius /= math.cos(math.radians(mesh["halfAngleDeg"] / mesh["nAng"]))
            eta = (radius - ri) / (ro - ri)
            if np.any((eta < 0) | (eta > 1)):
                raise ValueError("query falls outside the annulus")
            features = np.column_stack((np.full(len(radius), ri / ro), eta))
            velocity = data["velocity_m_s"][:, 2] / scale["velocity_m_s"]
            volumes = data["volume_m3"]
            gradient = float(data["driving_gradient_pa_m"])
        factor = scale["velocity_m_s"] * (360 / mesh["totalAngleDeg"]) / (physical["LengthMm"] * .001)
        analytical = np.array([
            U_analytical(r, ri, ro, physical["PressureGradientPaPerM"],
                         physical["DynamicViscosityPaS"]) / scale["velocity_m_s"]
            for r in radius
        ])

        unit = self.gradient_unit(scale["gradient_pa_m"], ri / ro)
        return Case(
            row["case_id"], row["split"], self.tensor(features), self.tensor(velocity),
            self.tensor(volumes / volumes.sum()), self.tensor(math.log(gradient / unit)),
            analytical, volumes, factor, physical["VolumetricFlowRateM3PerS"],
            unit, physical["PressureGradientPaPerM"],
        )

    def analytical_cases(self, training, n):
        ratios = sorted(float(case.inputs[0, 0]) for case in training)
        if n < len(ratios):
            raise ValueError("analytic case count must cover the CFD training ratios")
        # Keep the same shape range, and reserve complete validation, test and
        # edge bands even for generated labels. Start at the original ratios.
        candidates = np.linspace(ratios[0], ratios[-1], 20001)[1:-1]
        bands = [self.split_bands["validation"], self.split_bands["test"], *self.split_bands["edge"]]
        for low, high in bands:
            candidates = candidates[(candidates < low - .0025) | (candidates > high + .0025)]
        while len(ratios) < n:
            distance = np.min(np.abs(candidates[:, None] - ratios), axis=1)
            ratios.append(float(candidates[np.argmax(distance)]))
        eta = (np.arange(256) + .5) / 256
        cases = []
        for i, ratio in enumerate(sorted(ratios)):
            if any(low <= ratio <= high for low, high in bands):
                raise ValueError("the analytic generator entered a reserved split band")
            # Choose Ro=mu=Ubar=1 for the dimensionless solution.
            area_factor = 1 - ratio**2
            conductance = 1 - ratio**4 - area_factor**2 / math.log(1 / ratio)
            gradient = 8 * area_factor / conductance
            radius = ratio + eta * (1 - ratio)
            velocity = np.array([U_analytical(r, ratio, 1, gradient, 1) for r in radius])
            volume = 2 * math.pi * radius * (1 - ratio) / len(radius)
            unit = self.gradient_unit(1, ratio)
            cases.append(Case(
                f"analytic-{i:03d}", "train",
                self.tensor(np.column_stack((np.full(len(eta), ratio), eta))),
                self.tensor(velocity), self.tensor(volume / volume.sum()),
                self.tensor(math.log(gradient / unit)), velocity, volume, 1,
                math.pi * area_factor, unit, gradient,
            ))
        return cases

class ParameterMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.velocity = nn.Sequential(nn.Linear(2, 32), nn.Tanh(), nn.Linear(32, 32),
                                      nn.Tanh(), nn.Linear(32, 1))
        self.gradient = nn.Sequential(nn.Linear(1, 24), nn.Tanh(), nn.Linear(24, 1))

    def forward(self, features):
        eta = features[:, 1]
        profile = self.velocity(features).squeeze(-1)
        log_gradient = self.gradient(features[0, :1]).squeeze(-1)
        return 4 * eta * (1 - eta) * profile, log_gradient


def objective(prediction, case):
    velocity, gradient = prediction
    return ((velocity - case.velocity).square() @ case.weights
            + .1 * (gradient - case.log_gradient).square())


def measure(case, result):
    velocity, log_gradient = result
    prediction = velocity.cpu().double().numpy()
    reference = case.velocity.cpu().double().numpy()
    weights = case.physical_volumes
    analytical = case.analytical_velocity
    eta = case.inputs[:, 1].cpu().numpy()
    wall = (eta <= .1) | (eta >= .9)

    def norm(a, b):
        return 100 * math.sqrt(float(((a - b)**2 @ weights) / (b**2 @ weights)))

    def percent(a, b):
        return 100 * abs(a / b - 1)

    predicted_flow = float(prediction @ weights) * case.flow_factor
    predicted_gradient = math.exp(float(log_gradient)) * case.gradient_scale
    cfd_gradient = math.exp(float(case.log_gradient)) * case.gradient_scale
    return {
        "case_id": case.id, "split": case.split,
        "field_cfd_pct": norm(prediction, reference),
        "field_analytical_pct": norm(prediction, analytical),
        "cfd_analytical_pct": norm(reference, analytical),
        "wall_cfd_pct": 100 * float(np.max(np.abs(prediction[wall] - reference[wall]))) / float(reference.max()),
        "peak_cfd_pct": percent(prediction.max(), reference.max()),
        "flow_pct": percent(predicted_flow, case.imposed_flow),
        "gradient_cfd_pct": percent(predicted_gradient, cfd_gradient),
        "gradient_analytical_pct": percent(predicted_gradient, case.analytical_gradient),
        "cfd_gradient_analytical_pct": percent(cfd_gradient, case.analytical_gradient),
        "predicted_flow_m3_s": predicted_flow,
        "predicted_gradient_pa_m": predicted_gradient,
    }


def parameter_prediction(model, case):
    return model(case.inputs)


@torch.no_grad()
def evaluate(model, cases, predict=parameter_prediction):
    model.eval()
    results, losses = [], []
    for case in cases:
        prediction = predict(model, case)
        loss = float(objective(prediction, case))
        if not math.isfinite(loss):
            raise ValueError(f"{case.id}: nonfinite evaluation loss")
        losses.append(loss)
        results.append(measure(case, prediction))
    return sum(losses) / len(losses), results


def passed(results):
    return all(row[key] < limit for row in results for key, limit in LIMITS.items())


def fit(args, data, device, *, model_factory=ParameterMLP,
        model_name="Parameter MLP", predict=parameter_prediction, configuration=None):
    smoke = args.stage.endswith("-smoke")
    training = data.cases({"train"}, args.case if smoke else None)
    if args.analytic_cases:
        training = data.analytical_cases(training, args.analytic_cases)
    elif args.train_count:
        if args.train_count > len(training):
            raise ValueError("requested more CFD training cases than available")
        ordered = sorted(training, key=lambda case: float(case.inputs[0, 0]))
        selected = np.rint(np.linspace(0, len(ordered) - 1, args.train_count)).astype(int)
        training = [ordered[i] for i in selected]
    validation = training if smoke else data.cases({"validation"})
    updates_per_epoch = args.updates_per_epoch or len(training)
    commit = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = (args.runs or data.root / "runs") / f"{args.stage}-{stamp}"
    run_dir.mkdir(parents=True)
    started = time.perf_counter()
    receipt = {
        "model": model_name, "stage": args.stage, "status": "running",
        "split": "reconstruction" if smoke else "validation",
        "started_at": utc(), "updated_at": utc(), "commit": commit,
        "command": " ".join(sys.argv), "device": str(device), "seed": args.seed,
        "torch": torch.__version__, "epochs": args.epochs,
        "gradient_scale": data.gradient_scale,
        "training_source": "analytical" if args.analytic_cases else "CFD",
        "training_ratios": [float(case.inputs[0, 0]) for case in training],
        "updates_per_epoch": updates_per_epoch,
        "dataset_index_sha256": data.digest,
        "training_cases": [case.id for case in training],
        "validation_cases": [case.id for case in validation],
        "gate_limits_pct": LIMITS,
    }
    if configuration is not None:
        receipt["configuration"] = configuration
    write_json(str(run_dir / "run.json"), receipt)
    print(run_dir, flush=True)
    try:
        model = model_factory().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.003)
        order = np.random.default_rng(args.seed)
        def sample_indices():
            while True:
                yield from order.permutation(len(training))

        samples = sample_indices()
        best = math.inf
        with (run_dir / "metrics.jsonl").open("w") as metrics, (run_dir / "run.log").open("w") as log:
            for step in range(1, args.epochs + 1):
                model.train()
                losses = []
                for _ in range(updates_per_epoch):
                    case = training[next(samples)]
                    optimizer.zero_grad(set_to_none=True)
                    loss = objective(predict(model, case), case)
                    if not torch.isfinite(loss):
                        raise ValueError(f"{case.id}: nonfinite training loss")
                    loss.backward()
                    optimizer.step()
                    losses.append(float(loss.detach()))
                val_loss, rows = evaluate(model, validation, predict)
                metrics.write(json.dumps({
                    "step": step, "train_loss": sum(losses) / len(losses), "validation_loss": val_loss,
                    "max_flow_error_pct": max(row["flow_pct"] for row in rows),
                    "max_gradient_error_pct": max(row["gradient_cfd_pct"] for row in rows),
                }, allow_nan=False) + "\n")
                metrics.flush()
                if val_loss < best:
                    best, best_rows, best_step = val_loss, rows, step
                    # Only one final checkpoint is published at the end of the run.
                    # Use the PyTorch tensor state. NeuralOperator adds
                    # constructor metadata to its overridden state_dict;
                    # the run receipt already stores the model configuration.
                    best_weights = nn.Module.state_dict(model)
                    for name, parameter in best_weights.items():
                        best_weights[name] = parameter.detach().cpu().clone()
                if step == 1 or step % 20 == 0 or step == args.epochs:
                    log.write(f"epoch {step:4d} | val {val_loss:.5g} | "
                              f"flow max {max(row['flow_pct'] for row in rows):.3f}% | "
                              f"gradient max {max(row['gradient_cfd_pct'] for row in rows):.3f}%\n")
                    log.flush()
                    receipt["updated_at"] = utc()
                    write_json(str(run_dir / "run.json"), receipt)

        torch.save(best_weights, run_dir / "checkpoint.pt")
        write_json(str(run_dir / "validation.json"), {
            "selected_step": best_step, "loss": best, "limits_pct": LIMITS,
            "passed": passed(best_rows), "cases": best_rows,
        })
        receipt["status"] = ("smoke_passed" if smoke else "eligible_for_test") if passed(best_rows) else "gate_failed"
        receipt["checkpoint_sha256"] = sha256(run_dir / "checkpoint.pt")
        receipt["validation_sha256"] = sha256(run_dir / "validation.json")
        receipt["selected_step"] = best_step
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = str(error)
        with (run_dir / "run.log").open("a") as log:
            log.write(str(error) + "\n")
        raise
    finally:
        receipt["elapsed_s"] = time.perf_counter() - started
        receipt["updated_at"] = utc()
        write_json(str(run_dir / "run.json"), receipt)
    print(f"{receipt['status']} in {receipt['elapsed_s']:.2f} s")
    return int(receipt["status"] == "gate_failed")


def held_out(args, data, device):
    run_dir = args.run.resolve()
    receipt = read(run_dir / "run.json")
    if (receipt["stage"] != "mlp" or receipt["status"] != "eligible_for_test"
            or receipt["dataset_index_sha256"] != data.digest):
        raise ValueError("held-out evaluation needs a qualified supervised run on this dataset")
    output = run_dir / "held-out.json"
    if output.exists():
        raise ValueError(f"evaluation already published at {output}")
    checkpoint = checked_path(run_dir, "checkpoint.pt", receipt["checkpoint_sha256"])
    validation = checked_path(run_dir, "validation.json", receipt["validation_sha256"])
    if not read(validation)["passed"]:
        raise ValueError("checkpoint missed the validation gates")
    model = ParameterMLP().to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True))
    _, results = evaluate(model, data.cases({"test", "edge"}))
    write_json(str(output), {"checkpoint_sha256": receipt["checkpoint_sha256"],
                             "limits_pct": LIMITS, "passed": passed(results), "cases": results})
    print(output)
    return int(not passed(results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("mlp-smoke", "mlp", "mlp-evaluate"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--run", type=Path, help="qualified training run for held-out evaluation")
    parser.add_argument("--case", default="ann-7939f294", help="training case for the smoke diagnostic")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261118)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--gradient-scale", default="outer-radius", choices=("outer-radius", "gap"))
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--train-count", type=int, help="evenly spaced subset of the CFD training cases")
    sources.add_argument("--analytic-cases", type=int, help="use synthetic training profiles")
    parser.add_argument("--updates-per-epoch", type=int)
    args = parser.parse_args()
    if args.epochs <= 0 or (args.stage == "mlp-evaluate") != bool(args.run):
        parser.error("positive epochs required; --run is required only for mlp-evaluate")
    controls = (args.train_count, args.analytic_cases, args.updates_per_epoch)
    if any(value is not None and value <= 0 for value in controls):
        parser.error("case and update counts must be positive")
    if args.stage != "mlp" and any(value is not None for value in controls):
        parser.error("case and update count controls require the mlp stage")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable")
    device = torch.device(args.device)
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    scale = read(args.run / "run.json").get("gradient_scale", "outer-radius") if args.run else args.gradient_scale
    data = AnnulusData(args.dataset, device, scale)
    return held_out(args, data, device) if args.run else fit(args, data, device)


if __name__ == "__main__":
    raise SystemExit(main())
