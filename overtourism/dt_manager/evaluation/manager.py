# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    from overtourism.dt_manager.scenario.scenario import Scenario


class EvaluationManager:
    """Manage evaluation entities and their lifecycle.

    The manager owns creation, state transitions, and stored result payloads.
    The executor performs the actual model run and returns a JSON-like result.
    """

    def __init__(
        self,
        executor: Executor,
        store: Store | None = None,
        problem_id: str | None = None,
    ) -> None:
        """Create an evaluation manager bound to an executor."""
        self.executor = executor
        self.store = store
        self.problem_id = problem_id
        self.evaluations: dict[str, Evaluation] = {}
        self._session_evaluations: dict[str, Evaluation] = {}

    # ───────────────────────────────────────────────────────────
    # Lifecycle
    # ───────────────────────────────────────────────────────────

    def create_evaluation(
        self,
        evaluation_id: str,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        *,
        started: str | None = None,
    ) -> Evaluation:
        """Register a new running evaluation."""
        if evaluation_id in self.evaluations:
            raise EvaluationAlreadyExists(
                f"Evaluation with ID {evaluation_id} already exists"
            )

        evaluation = Evaluation.create_default(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
            state=EvaluationState.RUNNING,
        )
        self.evaluations[evaluation_id] = evaluation
        self._save_evaluation(evaluation)
        return evaluation

    def read_evaluation(self, evaluation_id: str) -> Evaluation:
        """Return a registered evaluation."""
        if evaluation_id not in self.evaluations:
            raise EvaluationDoesNotExist(
                f"Evaluation with ID {evaluation_id} does not exist"
            )
        return self.evaluations[evaluation_id]

    def list_evaluations(self, scenario_id: str | None = None) -> list[Evaluation]:
        """Return registered evaluations, optionally filtered by scenario."""
        evaluations = list(self.evaluations.values())
        if scenario_id is None:
            return evaluations
        return [
            evaluation
            for evaluation in evaluations
            if evaluation.scenario_id == scenario_id
        ]

    def read_latest_evaluation(self, scenario_id: str) -> Evaluation:
        """Return the most recently registered evaluation for a scenario."""
        for evaluation in reversed(list(self.evaluations.values())):
            if evaluation.scenario_id == scenario_id:
                return evaluation
        raise EvaluationDoesNotExist(
            f"Evaluation for scenario {scenario_id} does not exist"
        )

    def start_evaluation(self, evaluation_id: str) -> Evaluation:
        """Mark an evaluation as running."""
        evaluation = self.read_evaluation(evaluation_id)
        started = get_timestamp() if evaluation.started is None else evaluation.started
        return self._save_state(
            evaluation,
            state=EvaluationState.RUNNING,
            started=started,
            finished=None,
            result=None,
        )

    def complete_evaluation(self, evaluation_id: str, result: Any) -> Evaluation:
        """Mark an evaluation as completed and store its result."""
        evaluation = self.read_evaluation(evaluation_id)
        return self._save_state(
            evaluation,
            state=EvaluationState.COMPLETED,
            finished=get_timestamp(),
            result=result,
        )

    def fail_evaluation(
        self,
        evaluation_id: str,
        result: dict[str, Any] | None = None,
    ) -> Evaluation:
        """Mark an evaluation as failed and optionally keep a partial result."""
        evaluation = self.read_evaluation(evaluation_id)
        return self._save_state(
            evaluation,
            state=EvaluationState.FAILED,
            finished=get_timestamp(),
            result=result,
        )

    def delete_evaluation(self, evaluation_id: str) -> None:
        """Remove an evaluation from memory."""
        if evaluation_id not in self.evaluations:
            raise EvaluationDoesNotExist(
                f"Evaluation with ID {evaluation_id} does not exist"
            )
        self.evaluations.pop(evaluation_id)
        if self.store is not None and self.problem_id is not None:
            self.store.delete_evaluation(self.problem_id, evaluation_id)

    def delete_evaluations_for_scenario(self, scenario_id: str) -> None:
        """Remove all evaluations associated with a scenario from memory."""
        evaluation_ids = [
            evaluation_id
            for evaluation_id, evaluation in self.evaluations.items()
            if evaluation.scenario_id == scenario_id
        ]
        for evaluation_id in evaluation_ids:
            self.evaluations.pop(evaluation_id, None)
        self._session_evaluations = {
            session_id: evaluation
            for session_id, evaluation in self._session_evaluations.items()
            if evaluation.scenario_id != scenario_id
        }

    # ───────────────────────────────────────────────────────────
    # Persistence
    # ───────────────────────────────────────────────────────────

    def load_evaluations(self) -> list[Evaluation]:
        """Load evaluations from storage into memory."""
        if self.store is None or self.problem_id is None:
            return list(self.evaluations.values())
        evaluations = self.store.load_evaluations(self.problem_id)
        for evaluation in evaluations:
            if isinstance(evaluation.result, dict):
                evaluation.result = self.executor.model_evaluator.build_output(
                    evaluation.result
                )
        self.evaluations = {
            evaluation.evaluation_id: evaluation for evaluation in evaluations
        }
        return evaluations

    def load_evaluation(self, evaluation_id: str) -> Evaluation:
        """Load a single evaluation from storage into memory."""
        if self.store is None or self.problem_id is None:
            return self.read_evaluation(evaluation_id)
        evaluation = self.store.load_evaluation(self.problem_id, evaluation_id)
        if isinstance(evaluation.result, dict):
            evaluation.result = self.executor.model_evaluator.build_output(
                evaluation.result
            )
        self.evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def set_session_evaluation(self, session_id: str, evaluation: Evaluation) -> None:
        """Attach an in-memory evaluation to a transient session."""
        self._session_evaluations[session_id] = evaluation

    def save_session_evaluation(self, session_id: str) -> Evaluation:
        """Promote a transient session evaluation to persistent storage."""
        evaluation = self.read_session_evaluation(session_id)
        self.evaluations[evaluation.evaluation_id] = evaluation
        if self.store is not None and self.problem_id is not None:
            self.store.save_evaluation(
                self.problem_id, evaluation.evaluation_id, evaluation
            )
        return evaluation

    def read_session_evaluation(self, session_id: str) -> Evaluation:
        """Return the evaluation attached to a transient session."""
        if session_id not in self._session_evaluations:
            raise EvaluationDoesNotExist(
                f"Evaluation for session {session_id} does not exist"
            )
        return self._session_evaluations[session_id]

    def close_session(self, session_id: str) -> None:
        """Discard a transient session evaluation."""
        self._session_evaluations.pop(session_id, None)

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _save_evaluation(self, evaluation: Evaluation) -> None:
        if self.store is None or self.problem_id is None:
            return
        self.store.save_evaluation(
            self.problem_id, evaluation.evaluation_id, evaluation
        )

    def _save_state(
        self,
        evaluation: Evaluation,
        *,
        state: EvaluationState,
        started: str | None = None,
        finished: str | None = None,
        result: Any | None = None,
    ) -> Evaluation:
        """Apply a lifecycle state and persist the evaluation."""
        evaluation.state = state
        if started is not None:
            evaluation.started = started
        if finished is not None:
            evaluation.finished = finished
        evaluation.result = result
        self._save_evaluation(evaluation)
        return evaluation

    # ───────────────────────────────────────────────────────────
    # Execution
    # ───────────────────────────────────────────────────────────

    def run_evaluation(
        self,
        evaluation_id: str,
        scenario: Scenario,
        *,
        ensemble_size: int = 20,
        **kwargs: Any,
    ) -> Evaluation:
        """Execute an evaluation and persist the final state in memory."""
        self.start_evaluation(evaluation_id)
        try:
            result = self.executor.execute(
                scenario,
                ensemble_size=ensemble_size,
                **kwargs,
            )
        except Exception:
            self.fail_evaluation(evaluation_id)
            raise
        return self.complete_evaluation(evaluation_id, result)
