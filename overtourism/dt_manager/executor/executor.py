# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from overtourism.dt_manager.classes.model import ModelOutput
from overtourism.dt_manager.scenario.values import values_as_scipy

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
        **kwargs: Any,
    ) -> ModelOutput:
        """Run the evaluation and return a structured model output."""
        output = self.model_evaluator.evaluate(
            self.model,
            ensemble_size=ensemble_size,
            values=values_as_scipy(scenario),
            **kwargs,
        )
        if isinstance(output, dict):
            return self.model_evaluator.build_output(output)
        return output
