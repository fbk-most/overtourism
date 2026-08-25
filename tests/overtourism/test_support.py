# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from civic_digital_twins.dt_model.simulation.runner import ModelEvaluator

from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.utils.utils import get_timestamp

DEFAULT_TENANT = "tenant-alpha"
DEFAULT_PROBLEM_ID = f"{DEFAULT_TENANT}_base_problem"
DEFAULT_SCENARIO_ID = f"{DEFAULT_TENANT}_base_scenario"
DEFAULT_PROPOSAL_ID = f"{DEFAULT_TENANT}_base_proposal"


@dataclass(eq=False)
class FakeModelOutput:
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        self._model_version = None

    def to_dict(self) -> dict[str, Any]:
        return self.payload


class FakeModelEvaluator(ModelEvaluator):
    def __init__(self, model: Any = None) -> None:
        super().__init__(model or SimpleNamespace(name="fake-model", indexes=[]))
        self.evaluate_calls: list[dict[str, Any]] = []
        self.build_output_calls: list[dict[str, Any]] = []
        self._last_raw_values: dict[str, Any] = {}

    def input_schema(self) -> dict[str, dict[str, Any]]:
        return {}

    def _values_to_overrides(self, model: Any, values: dict[str, Any]) -> dict:
        self._last_raw_values = dict(values)
        return {}

    def evaluate(self, scenario: Any, config: Any) -> FakeModelOutput:
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


@dataclass
class RecordingViewer:
    widget_calls: list[tuple[dict[str, Any], str]] = field(default_factory=list)
    group_calls: list[list[str]] = field(default_factory=list)

    def get_widgets(
        self,
        values: dict[str, Any],
        language: str = "it",
    ) -> dict[str, Any]:
        snapshot = dict(values)
        self.widget_calls.append((snapshot, language))
        return {"summary": {"language": language, "values": snapshot}}

    def get_widget_ids_by_groups(self, groups: list[str]) -> list[str]:
        normalized_groups = list(groups)
        self.group_calls.append(normalized_groups)
        return [f"{group}-widget" for group in normalized_groups]


class FakeExecutionService:
    class Executor:
        def __init__(self, evaluator: FakeModelEvaluator) -> None:
            self.evaluator = evaluator

        def execute(self, scenario: Any, *, ensemble_size: int) -> FakeModelOutput:
            return self.evaluator.evaluate(
                scenario,
                SimpleNamespace(ensemble_size=ensemble_size),
            )

    def __init__(self, model: Any, model_evaluator: FakeModelEvaluator) -> None:
        self.model = model
        self.model_evaluator = model_evaluator
        self.executor = self.Executor(model_evaluator)

    def execute_evaluation(
        self,
        evaluation: Any,
        scenario: Any,
        *,
        ensemble_size: int = 20,
    ) -> Any:
        if evaluation.state is not EvaluationState.RUNNING:
            raise ValueError("Evaluation must be RUNNING")

        scenario._model = self.model
        self.model_evaluator._values_to_overrides(
            self.model,
            getattr(scenario, "param_overrides", {}),
        )
        try:
            result = self.executor.execute(scenario, ensemble_size=ensemble_size)
        except Exception:
            evaluation.state = EvaluationState.FAILED
            evaluation.finished = get_timestamp()
            evaluation.version += 1
            raise

        evaluation.state = EvaluationState.COMPLETED
        evaluation.finished = get_timestamp()
        evaluation.version += 1
        evaluation.result = result
        return evaluation


def bootstrap_default_entities(manager: Any, tenant: str = DEFAULT_TENANT) -> None:
    manager.problem_manager.create_problem(
        DEFAULT_PROBLEM_ID,
        tenant=tenant,
        name="Base problem",
        description="Base problem",
    )
    manager.scenario_manager.create_scenario(
        DEFAULT_SCENARIO_ID,
        tenant,
        param_overrides={"visits": 0},
        name="Base scenario",
        description="Base scenario",
    )
    manager.proposal_manager.create_proposal(
        DEFAULT_PROPOSAL_ID,
        DEFAULT_PROBLEM_ID,
        name="Base proposal",
        description="Base proposal",
        status="draft",
    )
    manager.relationship_manager.link_scenario_proposal(
        DEFAULT_PROPOSAL_ID,
        DEFAULT_SCENARIO_ID,
    )
