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
    from overtourism.dt_manager.classes.model import ModelOutput
    from overtourism.dt_manager.scenario.scenario import Scenario


class EvaluationManager:
    """Manage evaluation entities and their lifecycle.

    The manager owns creation, state transitions, and stored result payloads.
    The executor performs the actual model run and returns a JSON-like result.
    """

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
        self.save_evaluation(evaluation)
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
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_evaluation(self, evaluation: Evaluation) -> None:
        self.store.save_evaluation(
            self.problem_id,
            evaluation.evaluation_id,
            evaluation,
        )

    def load_evaluations(self) -> list[Evaluation]:
        """Load evaluations from storage into memory."""
        evaluations = [
            self._normalize_loaded_evaluation(evaluation)
            for evaluation in self.store.load_evaluations(self.problem_id)
        ]
        self.evaluations = {
            evaluation.evaluation_id: evaluation for evaluation in evaluations
        }
        return evaluations

    def load_evaluation(self, evaluation_id: str) -> Evaluation:
        """Load a single evaluation from storage into memory."""
        evaluation = self._normalize_loaded_evaluation(
            self.store.load_evaluation(self.problem_id, evaluation_id)
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
        self.save_evaluation(evaluation)
        return evaluation

    def create_session_evaluation(
        self,
        session_id: str,
        evaluation_id: str,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        *,
        started: str | None = None,
    ) -> Evaluation:
        """Create a transient evaluation for a session."""
        if session_id in self._session_evaluations:
            raise EvaluationAlreadyExists(
                f"Evaluation for session {session_id} already exists"
            )

        evaluation = Evaluation.create_default(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
            state=EvaluationState.RUNNING,
        )
        self._session_evaluations[session_id] = evaluation
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
        return self._execute(
            scenario,
            evaluation_id=evaluation_id,
            ensemble_size=ensemble_size,
            **kwargs,
        )

    def run_session_evaluation(
        self,
        session_id: str,
        scenario: Scenario,
        *,
        ensemble_size: int = 20,
        **kwargs: Any,
    ) -> Evaluation:
        """Execute a transient evaluation and keep it in session memory only."""
        return self._execute(
            scenario,
            ensemble_size=ensemble_size,
            session_id=session_id,
            **kwargs,
        )

    def _execute(
        self,
        scenario: Scenario,
        ensemble_size: int = 20,
        evaluation_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Evaluation:
        try:
            result = self.executor.execute(
                scenario,
                ensemble_size=ensemble_size,
                **kwargs,
            )
        except Exception:
            self._finish_evaluation(
                state=EvaluationState.FAILED,
                evaluation_id=evaluation_id,
                session_id=session_id,
            )
            raise
        return self._finish_evaluation(
            state=EvaluationState.COMPLETED,
            evaluation_id=evaluation_id,
            result=result,
            session_id=session_id,
        )

    def _finish_evaluation(
        self,
        state: EvaluationState,
        evaluation_id: str | None = None,
        session_id: str | None = None,
        result: ModelOutput | None = None,
    ) -> Evaluation:
        if session_id is not None:
            evaluation = self.read_session_evaluation(session_id)
        else:
            evaluation = self.read_evaluation(evaluation_id)

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

        if session_id is None:
            self.save_evaluation(evaluation)

        return evaluation

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _normalize_loaded_evaluation(self, evaluation: Evaluation) -> Evaluation:
        if isinstance(evaluation.result, dict):
            evaluation.result = self.executor.model_evaluator.build_output(
                evaluation.result
            )
        return evaluation
