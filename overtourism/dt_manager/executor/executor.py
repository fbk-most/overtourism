# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

from overtourism.dt_manager.scenario.values import values_as_scipy
from overtourism.overtourism.molveno_runner import MolvenoConfig, MolvenoOutput

if TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model

    from overtourism.dt_manager.classes.model import ModelEvaluator
    from overtourism.dt_manager.scenario.scenario import Scenario


class Executor:
    """Run scenario evaluations without mutating storage."""

    def __init__(self, model: Model, model_evaluator: ModelEvaluator) -> None:
        """Create an executor bound to a model and evaluator."""
        self.model = model
        self.model_evaluator = model_evaluator

    def execute(
        self,
        scenario: Scenario,
        *,
        ensemble_size: int = 20,
        context_id: str | None = None,
        **kwargs: Any,
    ) -> MolvenoOutput:
        """Run the evaluation and return a structured model output."""
        # Translate dt_manager Scenario → CDT index overrides
        raw_values = values_as_scipy(scenario)
        overrides = self.model_evaluator._values_to_overrides(self.model, raw_values)
        cdt_scenario = CDTScenario(self.model, overrides=overrides)
        config = MolvenoConfig(ensemble_size=ensemble_size, context_id=context_id)
        return self.model_evaluator.evaluate(cdt_scenario, config)
