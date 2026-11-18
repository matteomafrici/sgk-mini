#!/usr/bin/env python3
"""Meridional-grid FNO with the same native CFD evaluator as the parameter MLP."""

import argparse
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from train_annulus import AnnulusData, Case, DEFAULT, checked_path, fit, read
from validate_annulus import structured_axis

GRID = (65, 32)
TRANSFER_LIMITS = {"field_pct": 0.2, "wall_pct": 0.3, "flow_pct": 0.1}
CONFIG = {"grid": list(GRID), "modes": [8, 8], "width": 16, "layers": 3,
          "input_channels": ["VDB signed distance/gap", "radial gap coordinate", "Ri/Ro"],
          "gradient": "mean decoded log gradient on the grid"}


@dataclass
class GridCase(Case):
    meridional: torch.Tensor
    queries: torch.Tensor
    transferred: torch.Tensor


def at_queries(field, queries):
    return F.grid_sample(field[None, None], queries, mode="bilinear",
                         padding_mode="border", align_corners=True)[0, 0, :, 0]


class GridData(AnnulusData):
    def load_case(self, row):
        case = super().load_case(row)
        metadata = read(checked_path(self.inputs, row["metadata"], row["metadata_sha256"]))
        record = read(checked_path(self.root, metadata["source_record"],
                                   metadata["source_record_sha256"]))
        mesh = record["reference"]["report"]["mesh"]
        if mesh["nAng"] != 1:
            raise ValueError("the meridional adapter requires a single wedge layer")
        geometry = record["geometry"]["physical"]
        ri, ro, length = [geometry[key] * .001
                          for key in ("InnerRadiusMm", "OuterRadiusMm", "LengthMm")]
        gap = ro - ri
        eta_nodes = np.linspace(0, 1, GRID[0])
        z_nodes = np.linspace(0, length, GRID[1])
        with np.load(checked_path(self.inputs, row["arrays"], row["arrays_sha256"]), allow_pickle=False) as src:
            points = src["query_xyz_m"]
            radius = np.linalg.norm(points[:, :2], axis=1) / np.cos(np.deg2rad(mesh["halfAngleDeg"]))
            axial = points[:, 2]
            sdf = src["grid_sdf_m"]
            x_axis, y_axis, z_axis = (src[key] for key in ("grid_x_m", "grid_y_m", "grid_z_m"))

        # Recover the VDB-derived meridional plane at x=0 by interpolating
        # between the two stored transverse planes closest to the axis.
        right = np.searchsorted(x_axis, 0)
        fraction = -x_axis[right - 1] / (x_axis[right] - x_axis[right - 1])
        x_zero = (1 - fraction) * sdf[right - 1] + fraction * sdf[right]
        along_r = np.column_stack([
            np.interp(ri + gap * eta_nodes, y_axis, x_zero[:, i])
            for i in range(len(z_axis))
        ])
        spatial = np.stack([np.interp(z_nodes, z_axis, profile) for profile in along_r]) / gap
        meridional = np.stack((spatial, np.broadcast_to(eta_nodes[:, None], GRID),
                               np.full(GRID, ri / ro)))

        n_axial, n_radial = mesh["nX"], mesh["nR1"] + mesh["nR2"]
        z_stations, z_index = structured_axis(axial, n_axial, n_radial)
        r_stations, r_index = structured_axis(radius, n_radial, n_axial)
        native = np.full((n_radial, n_axial), np.nan)
        native[r_index, z_index] = case.velocity.cpu().numpy()
        if not np.all(np.isfinite(native)):
            raise ValueError("native samples do not fill the expected grid")

        radial_nodes = np.r_[ri, r_stations, ro]
        nodal_profiles = np.pad(native, ((1, 1), (0, 0)))
        reference_grid = np.column_stack([
            np.interp(ri + gap * eta_nodes, radial_nodes, nodal_profiles[:, station])
            for station in range(n_axial)
        ])
        # The OpenFOAM case is axially periodic. Extend the two end stations
        # across the seam to interpolate instead of extrapolating there.
        axial_nodes = np.r_[z_stations[-1] - length, z_stations, z_stations[0] + length]
        periodic = np.pad(reference_grid, ((0, 0), (1, 1)), mode="wrap")
        regular = np.stack([np.interp(z_nodes, axial_nodes, line) for line in periodic])
        queries = self.tensor(np.column_stack((2 * axial / length - 1, 2 * (radius - ri) / gap - 1))
                              .reshape(1, -1, 1, 2))
        transferred = at_queries(self.tensor(regular), queries)
        return GridCase(**vars(case), meridional=self.tensor(meridional),
                        queries=queries, transferred=transferred)


def transfer_checks(cases):
    results = []
    for case in cases:
        estimate = case.transferred.cpu().numpy().astype(float)
        reference = case.velocity.cpu().numpy().astype(float)
        eta = case.inputs[:, 1].cpu().numpy()
        wall = (eta <= .1) | (eta >= .9)
        weights = case.physical_volumes
        result = {
            "field_pct": 100 * np.sqrt(((estimate-reference)**2 @ weights) / (reference**2 @ weights)),
            "wall_pct": 100 * np.max(np.abs(estimate[wall]-reference[wall])) / reference.max(),
            "flow_pct": 100 * abs((estimate @ weights) / (reference @ weights) - 1),
        }
        results.append(result)
        print(case.id, " ".join(f"{key}={value:.5f}%" for key, value in result.items()))
    maxima = {key: max(row[key] for row in results) for key in TRANSFER_LIMITS}
    print("Transfer maxima:", " ".join(f"{key}={value:.5f}%" for key, value in maxima.items()), flush=True)
    if any(not np.isfinite(value) or value >= TRANSFER_LIMITS[key] for key, value in maxima.items()):
        raise ValueError("CFD to grid transfer did not pass the declared error budget")


def make_fno():
    from neuralop.models import FNO
    return FNO(n_modes=tuple(CONFIG["modes"]), in_channels=3, out_channels=2,
               hidden_channels=CONFIG["width"], n_layers=CONFIG["layers"],
               positional_embedding=None)


def predict_grid(model, case):
    output = model(case.meridional[None])[0]
    eta = case.meridional[1]
    field = 4 * eta * (1 - eta) * output[0]
    return at_queries(field, case.queries), output[1].mean()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("grid-check", "fno-smoke", "fno"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--case", default="ann-7939f294")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261118)
    args = parser.parse_args()
    if args.epochs < 1 or (args.device == "cuda" and not torch.cuda.is_available()):
        parser.error("positive epoch count and an available device are required")
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    data = GridData(args.dataset, device, "gap")
    if args.stage == "grid-check":
        transfer_checks(data.cases({"train", "validation"}))
        return 0
    if args.stage == "fno-smoke":
        transfer_checks(data.cases({"train"}, args.case))
    else:
        transfer_checks(data.cases({"train", "validation"}))
    args.analytic_cases = args.train_count = args.updates_per_epoch = None
    return fit(args, data, device, model_factory=make_fno, model_name="Meridional FNO",
               predict=predict_grid, configuration=CONFIG | {"neuraloperator": version("neuraloperator")})


if __name__ == "__main__":
    raise SystemExit(main())
