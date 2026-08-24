# SPDX-License-Identifier: Apache-2.0
"""Pydantic request/response models for the REST API.

`EvaluateResponse` is a purpose-built plain-JSON response shape — not
`SustainabilityFieldOutput.to_snapshot()`. `to_snapshot()` (via the
`civic_digital_twins` library's `ModelOutput._serialize()`) base64+dtype+
shape-encodes array fields, which is the right format for Layer 4
persistence/resume but not a good REST wire format: Layer 4's own consumer
expects plain JSON matching the shape of the model's previous evaluator
output (see `overtourism/BACKEND_DESIGN.md` — Layer 5 REST API), so
`EvaluateResponse` mirrors `SustainabilityFieldOutput`'s full field set,
including the derived usage/uncertainty/KPI fields, as plain lists/dicts.
"""

from __future__ import annotations

from typing import Any

from overtourism.model.common.sustainability_field import SustainabilityFieldOutput
from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """One entry in the `GET /models` catalogue."""

    key: str
    title: str


class EvaluateRequest(BaseModel):
    """Body of `POST /models/{model_key}/evaluate`.

    `param_overrides` mirrors `Backend.evaluate()`'s signature: a partial
    `{index_name: value}` mapping. Scalars are `float`, distributions are
    `(lo, hi)` pairs (JSON arrays of length 2), categoricals are `str`. Keys
    absent from the mapping use model defaults.
    """

    param_overrides: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    """Plain-JSON evaluation result — see module docstring for why this
    is not `SustainabilityFieldOutput.to_snapshot()`.
    """

    field: list[list[float]]
    field_elements: dict[str, list[list[float]]]
    x_values: list[float]
    y_values: list[float]
    x_axis_name: str
    y_axis_name: str
    samples_x: list[float]
    samples_y: list[float]
    confidence: float
    sustainable_area: float
    sustainability_index: dict[str, float]
    sustainability_by_constraint: dict[str, dict[str, float]]
    modal_lines: dict[str, dict[str, list[float]]]
    x_max: float
    y_max: float
    uncertainty: list[float]
    uncertainty_by_constraint: dict[str, list[float]]
    usage: list[int]
    usage_by_constraint: dict[str, list[int]]
    usage_uncertainty: list[float]
    usage_uncertainty_by_constraint: dict[str, list[float]]
    capacity_mean: float
    capacity_mean_by_constraint: dict[str, float]
    kpis: dict[str, Any]
    constraint_curves: dict[str, list[list[float]]]

    @classmethod
    def from_output(cls, output: SustainabilityFieldOutput) -> EvaluateResponse:
        """Build a response from a live `SustainabilityFieldOutput`."""
        idx, ci = output.sustainability_index
        return cls(
            field=output.field.tolist(),
            field_elements={k: v.tolist() for k, v in output.field_elements.items()},
            x_values=output.x_values.tolist(),
            y_values=output.y_values.tolist(),
            x_axis_name=output.x_axis_name,
            y_axis_name=output.y_axis_name,
            samples_x=output.samples_x,
            samples_y=output.samples_y,
            confidence=output.confidence,
            sustainable_area=output.sustainable_area,
            sustainability_index={"value": idx, "ci": ci},
            sustainability_by_constraint={
                k: {"value": v, "ci": c}
                for k, (v, c) in output.sustainability_by_constraint.items()
            },
            modal_lines={
                k: {"x": x.tolist(), "y": y.tolist()}
                for k, (x, y) in output.modal_lines.items()
            },
            x_max=output.x_max,
            y_max=output.y_max,
            uncertainty=output.uncertainty,
            uncertainty_by_constraint=output.uncertainty_by_constraint,
            usage=output.usage,
            usage_by_constraint=output.usage_by_constraint,
            usage_uncertainty=output.usage_uncertainty,
            usage_uncertainty_by_constraint=output.usage_uncertainty_by_constraint,
            capacity_mean=output.capacity_mean,
            capacity_mean_by_constraint=output.capacity_mean_by_constraint,
            kpis=output.kpis,
            constraint_curves=output.constraint_curves,
        )
