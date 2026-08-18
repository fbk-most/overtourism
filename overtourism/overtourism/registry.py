# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from civic_digital_twins.dt_model.simulation.runner import EvaluationConfig
from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

from overtourism.dt_manager.evaluation.evaluation import Evaluation, EvaluationState
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.scenario.values import values_as_scipy
from overtourism.dt_manager.utils.utils import get_timestamp

if TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model
    from civic_digital_twins.dt_model.simulation.runner import (
        ModelEvaluator,
        ModelOutput,
    )

    from overtourism.dt_manager.scenario.scenario import Scenario


class ModelExecutionService:
    """Execute model workflows for a single tenant."""

    def __init__(
        self,
        tenant: str,
        model: Model,
        model_evaluator: ModelEvaluator,
    ) -> None:
        self.tenant = tenant
        self.model = model
        self.model_evaluator = model_evaluator
        self.executor = Executor(model, model_evaluator)

    def scenario_index_diffs(self, scenario: Scenario) -> dict[str, str]:
        raw_values = values_as_scipy(scenario)
        overrides = self.model_evaluator._values_to_overrides(self.model, raw_values)
        cdt_scenario = CDTScenario(self.model, overrides=overrides)
        return self.model_evaluator.get_index_diffs(cdt_scenario)

    def model_values(self) -> dict[str, Any]:
        cdt_scenario = CDTScenario(self.model)
        return self.model_evaluator.get_model_values(cdt_scenario)

    def execute_evaluation(
        self,
        evaluation: Evaluation,
        scenario: Scenario,
        *,
        ensemble_size: int = 20,
        **kwargs: Any,
    ) -> Evaluation:
        try:
            result = self.executor.execute(
                scenario,
                evaluation_config=EvaluationConfig,
                ensemble_size=ensemble_size,
                **kwargs,
            )
        except Exception:
            self._finish_evaluation_object(
                evaluation,
                state=EvaluationState.FAILED,
            )
            raise

        return self._finish_evaluation_object(
            evaluation,
            state=EvaluationState.COMPLETED,
            result=result,
        )

    def _finish_evaluation_object(
        self,
        evaluation: Evaluation,
        state: EvaluationState,
        result: ModelOutput | None = None,
    ) -> Evaluation:
        if evaluation.state != EvaluationState.RUNNING:
            raise ValueError(
                f"Evaluation {evaluation.evaluation_id} must be {EvaluationState.RUNNING} to finish"
            )

        evaluation.state = state
        evaluation.finished = get_timestamp()
        evaluation.result = result
        evaluation.version += 1

        return evaluation


class ExecutionManagerRegistry:
    """Tenant-aware registry for execution services."""

    def __init__(self) -> None:
        self._services: dict[str, ModelExecutionService] = {}
        self._default_tenant: str | None = None

    def register(self, service: ModelExecutionService) -> None:
        self._services[service.tenant] = service
        if self._default_tenant is None:
            self._default_tenant = service.tenant

    def get(self, tenant: str) -> ModelExecutionService:
        return self._services[tenant]

    @property
    def default_tenant(self) -> str | None:
        return self._default_tenant

    def tenants(self) -> list[str]:
        return list(self._services)
