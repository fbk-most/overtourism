# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from overtourism.dt_manager.classes.model import ModelEvaluator, ModelOutput


@dataclass
class FakeModelOutput(ModelOutput):
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.payload


class FakeModelEvaluator(ModelEvaluator):
    def __init__(self) -> None:
        self.evaluate_calls: list[dict[str, Any]] = []
        self.build_output_calls: list[dict[str, Any]] = []

    def evaluate(self, model, *, ensemble_size: int, **kwargs: Any) -> dict[str, Any]:
        call = {"model": model, "ensemble_size": ensemble_size, **kwargs}
        self.evaluate_calls.append(call)
        return {"ensemble_size": ensemble_size, "values": kwargs.get("values", {})}

    def build_output(self, data: dict[str, Any]) -> ModelOutput:
        self.build_output_calls.append(data)
        return FakeModelOutput(data)

    def get_index_diffs(self, model, values: dict | None = None) -> dict[str, str]:
        return {}

    def get_model_values(self, model) -> dict[str, Any]:
        return {}


@pytest.fixture
def fake_model() -> SimpleNamespace:
    return SimpleNamespace(name="fake-model")


@pytest.fixture
def fake_model_evaluator() -> FakeModelEvaluator:
    return FakeModelEvaluator()
