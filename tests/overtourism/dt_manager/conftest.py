# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from civic_digital_twins.dt_model.simulation.runner import (
    EvaluationConfig,
    ModelEvaluator,
    ModelOutput,
)


@dataclass(eq=False)
class FakeModelOutput(ModelOutput):
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        super().__init__()

    def to_dict(self) -> dict[str, Any]:
        """Return only the domain payload — omits dt_model_version for test simplicity."""
        return self.payload

    def _serialize(self) -> dict[str, Any]:
        return self.payload


class FakeModelEvaluator(ModelEvaluator):
    def __init__(self, model: Any = None) -> None:
        super().__init__(model or SimpleNamespace(name="fake", indexes=[]))
        self.evaluate_calls: list[dict[str, Any]] = []
        self.build_output_calls: list[dict[str, Any]] = []
        self._last_raw_values: dict[str, Any] = {}

    def input_schema(self) -> dict[str, dict[str, Any]]:
        return {}

    def _values_to_overrides(self, model: Any, values: dict[str, Any]) -> dict:
        # Stash raw values so evaluate() can include them in its call record.
        self._last_raw_values = dict(values)
        return {}

    def evaluate(self, scenario: Any, config: EvaluationConfig) -> FakeModelOutput:
        values = self._last_raw_values
        call = {
            "model": getattr(scenario, "_model", None),
            "ensemble_size": config.ensemble_size,
            "values": values,
        }
        self.evaluate_calls.append(call)
        return FakeModelOutput(
            {"ensemble_size": config.ensemble_size, "values": values}
        )

    def build_output(self, data: dict[str, Any]) -> FakeModelOutput:
        self.build_output_calls.append(data)
        return FakeModelOutput(data)

    def get_index_diffs(self, scenario: Any) -> dict[str, str]:  # type: ignore[override]
        return {}

    def get_model_values(self, scenario: Any) -> dict[str, Any]:  # type: ignore[override]
        return {}


@pytest.fixture
def fake_model() -> SimpleNamespace:
    return SimpleNamespace(name="fake-model", indexes=[])


@pytest.fixture
def fake_model_evaluator() -> FakeModelEvaluator:
    return FakeModelEvaluator()
