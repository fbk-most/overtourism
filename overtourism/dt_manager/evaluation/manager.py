# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from civic_digital_twins.dt_model.simulation.runner import EvaluationConfig

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
    EvaluationState,
)
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    EvaluationAlreadyExists,
    EvaluationDoesNotExist,
)
from overtourism.dt_manager.utils.utils import get_timestamp

if TYPE_CHECKING:
    from civic_digital_twins.dt_model.simulation.runner import ModelOutput

    from overtourism.dt_manager.scenario.scenario import Scenario


class EvaluationManager:
    """Manage evaluation entities and their lifecycle."""

    def __init__(
        self,
        store: Store,
        problem_id: str,
        executor: Executor,
    ) -> None:
        """Create an evaluation manager bound to an executor."""
        self.executor = executor
        self.store = store
        self.problem_id = problem_id

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_evaluation(
        self,
        evaluation_id: str,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        *,
        started: str | None = None,
    ) -> Evaluation:
        """Create and persist a new running evaluation."""
        try:
            self.store.load_evaluation(self.problem_id, evaluation_id)
        except EvaluationDoesNotExist:
            pass
        else:
            raise EvaluationAlreadyExists(
                f"Evaluation with ID {evaluation_id} already exists"
            )

        evaluation = self.build_running_evaluation(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
        )
        self.save_evaluation(evaluation)
        return evaluation

    def read_evaluation(self, evaluation_id: str) -> Evaluation:
        """Return a persisted evaluation."""
        return self._build_evaluation(
            self.store.load_evaluation(self.problem_id, evaluation_id)
        )

    def list_evaluations(self, scenario_id: str | None = None) -> list[Evaluation]:
        """Return persisted evaluations, optionally filtered by scenario."""
        evaluations = [
            self._build_evaluation(evaluation)
            for evaluation in self.store.load_evaluations(self.problem_id)
        ]
        if scenario_id is None:
            return evaluations
        return [
            evaluation
            for evaluation in evaluations
            if evaluation.scenario_id == scenario_id
        ]

    def read_latest_evaluation(self, scenario_id: str) -> Evaluation:
        """Return the most recently registered persisted evaluation."""
        evaluations = [
            evaluation
            for evaluation in self.store.load_evaluations(self.problem_id)
            if evaluation["scenario_id"] == scenario_id
        ]
        if evaluations:
            latest = max(
                evaluations,
                key=lambda evaluation: (
                    evaluation.get("started") or "",
                    evaluation["evaluation_id"],
                ),
            )
            return self._build_evaluation(latest)
        raise EvaluationDoesNotExist(
            f"Evaluation for scenario {scenario_id} does not exist"
        )

    def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete a persisted evaluation."""
        self.read_evaluation(evaluation_id)
        self.store.delete_evaluation(self.problem_id, evaluation_id)

    def delete_evaluations_for_scenario(self, scenario_id: str) -> None:
        """Remove all persisted evaluations for a scenario."""
        for evaluation in self.list_evaluations(scenario_id):
            try:
                self.store.delete_evaluation(
                    self.problem_id,
                    evaluation.evaluation_id,
                )
            except EvaluationDoesNotExist:
                pass

    # ───────────────────────────────────────────────────────────
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_evaluation(self, evaluation: Evaluation) -> None:
        self.store.save_evaluation(
            self.problem_id,
            evaluation.evaluation_id,
            evaluation.to_dict(),
        )

    def build_running_evaluation(
        self,
        evaluation_id: str,
        *,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        started: str | None = None,
    ) -> Evaluation:
        """Build a running evaluation without persisting it."""
        return Evaluation.create_default(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
            state=EvaluationState.RUNNING,
        )

    # ───────────────────────────────────────────────────────────
    # Execution
    # ───────────────────────────────────────────────────────────

    def run_evaluation(
        self,
        evaluation_id: str,
        scenario: Scenario,
        *,
        evaluation_config: type[EvaluationConfig] = EvaluationConfig,
        **kwargs: Any,
    ) -> Evaluation:
        """Execute an evaluation and persist the final state in memory."""
        evaluation = self.read_evaluation(evaluation_id)
        return self.execute_evaluation(
            evaluation,
            scenario,
            evaluation_config=evaluation_config,
            persist=True,
            **kwargs,
        )

    def rerun_evaluation(
        self,
        evaluation_id: str,
        scenario: Scenario,
        *,
        evaluation_config: type[EvaluationConfig] = EvaluationConfig,
        **kwargs: Any,
    ) -> Evaluation:
        """Re-execute a persisted evaluation in place."""
        evaluation = self.read_evaluation(evaluation_id)
        return self.rerun_evaluation_object(
            evaluation,
            scenario,
            evaluation_config=evaluation_config,
            persist=True,
            **kwargs,
        )

    def rerun_evaluation_object(
        self,
        evaluation: Evaluation,
        scenario: Scenario,
        *,
        evaluation_config: type[EvaluationConfig] = EvaluationConfig,
        persist: bool = False,
        **kwargs: Any,
    ) -> Evaluation:
        """Re-execute an existing evaluation object with a fresh running state."""
        restarted = Evaluation.create_default(
            evaluation.evaluation_id,
            scenario_id=evaluation.scenario_id,
            type=evaluation.type,
            version=evaluation.version,
        )
        return self.execute_evaluation(
            restarted,
            scenario,
            evaluation_config=evaluation_config,
            persist=persist,
            **kwargs,
        )

    def execute_evaluation(
        self,
        evaluation: Evaluation,
        scenario: Scenario,
        *,
        evaluation_config: type[EvaluationConfig] = EvaluationConfig,
        persist: bool = False,
        **kwargs: Any,
    ) -> Evaluation:
        """Execute an evaluation object and optionally persist the result."""
        try:
            result = self.executor.execute(
                scenario,
                evaluation_config=evaluation_config,
                **kwargs,
            )
        except Exception:
            self._finish_evaluation_object(
                evaluation,
                state=EvaluationState.FAILED,
                persist=persist,
            )
            raise
        return self._finish_evaluation_object(
            evaluation,
            state=EvaluationState.COMPLETED,
            result=result,
            persist=persist,
        )

    def _finish_evaluation_object(
        self,
        evaluation: Evaluation,
        state: EvaluationState,
        result: ModelOutput | None = None,
        *,
        persist: bool = False,
    ) -> Evaluation:
        # Only allow finishing evaluations that are currently running,
        # to prevent accidental state changes on completed or failed evaluations.
        if evaluation.state != EvaluationState.RUNNING:
            raise ValueError(
                f"Evaluation {evaluation.evaluation_id} must be {EvaluationState.RUNNING} to finish"
            )

        # Update the evaluation state and timestamps, then persist the changes.
        evaluation.state = state
        evaluation.finished = get_timestamp()
        evaluation.result = result
        evaluation.version += 1

        if persist:
            self.save_evaluation(evaluation)

        return evaluation

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _build_evaluation(self, evaluation_data: dict) -> Evaluation:
        evaluation = Evaluation.from_dict(evaluation_data)
        if isinstance(evaluation.result, dict) and hasattr(
            self.executor.model_evaluator, "build_output"
        ):
            evaluation.result = self.executor.model_evaluator.build_output(
                evaluation.result
            )
        return evaluation
