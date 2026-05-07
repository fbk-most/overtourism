# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from dataclasses import dataclass

from overtourism.dt_manager.classes.model import ModelOutput


@dataclass
class OvertourismOutputData(ModelOutput):
    """Container for overtourism evaluation results (mirrors old config.classes.ModelOutput)."""

    x_max: int
    y_max: int
    sample_x: list[float]
    sample_y: list[float]
    kpis: dict[str, float]
    uncertainty: list[float]
    uncertainty_by_constraint: dict[str, list[float]]
    constraint_curves: dict[str, list[float]]
    usage: list[float]
    usage_by_constraint: dict[str, list[float]]
    usage_uncertainty: list[float]
    usage_uncertainty_by_constraint: dict[str, list[float]]
    capacity_mean: float
    capacity_mean_by_constraint: dict[str, float]

    def to_dict(self) -> dict[str, typing.Any]:
        """Convert the output data to a dictionary."""
        return self.__dict__
