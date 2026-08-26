# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
    EvaluationState,
)
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    EvaluationAlreadyExists,
)
from overtourism.dt_manager.utils.utils import get_timestamp


class EvaluationManager:
    """Manage evaluation entities and their lifecycle."""

    def __init__(self, store: Store) -> None:
        self.store = store

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
        """Create and persist a new evaluation."""
        try:
            self.store.load_evaluation(evaluation_id)
        except EntityDoesNotExist:
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
        self.store.save_evaluation(evaluation.to_dict())
        return evaluation

    def read_evaluation(
        self,
        evaluation_id: str,
        tenant: str | None = None,
    ) -> Evaluation:
        """Return a persisted evaluation."""
        return Evaluation.from_dict(
            self.store.load_evaluation(evaluation_id, tenant=tenant)
        )

    def list_evaluations(
        self,
        scenario_id: str | None = None,
        tenant: str | None = None,
    ) -> list[Evaluation]:
        """Return persisted evaluations, optionally filtered by scenario."""
        return [
            Evaluation.from_dict(evaluation)
            for evaluation in self.store.load_evaluations(
                scenario_id,
                tenant=tenant,
            )
        ]

    def read_latest_evaluation(
        self,
        scenario_id: str,
        tenant: str | None = None,
    ) -> Evaluation:
        """Return the most recently registered persisted evaluation."""
        evaluations = self.list_evaluations(scenario_id, tenant=tenant)
        if evaluations:
            return max(
                evaluations,
                key=lambda evaluation: (
                    evaluation.started or "",
                    evaluation.evaluation_id,
                ),
            )
        raise EntityDoesNotExist(
            f"Evaluation for scenario {scenario_id} does not exist"
        )

    def update_evaluation(self, evaluation: Evaluation) -> None:
        """Update a persisted evaluation."""
        self.read_evaluation(evaluation.evaluation_id)
        self.store.save_evaluation(evaluation.to_dict())

    def complete_evaluation(
        self,
        evaluation: Evaluation,
        result: Any,
    ) -> Evaluation:
        """Mark a running evaluation as completed and persist its result."""
        if evaluation.state is not EvaluationState.RUNNING:
            raise ValueError("Evaluation must be RUNNING")

        evaluation.result = result
        evaluation.state = EvaluationState.COMPLETED
        evaluation.finished = get_timestamp()
        self.update_evaluation(evaluation)
        return evaluation

    def fail_evaluation(self, evaluation: Evaluation) -> Evaluation:
        """Mark a running evaluation as failed and persist its state."""
        if evaluation.state is not EvaluationState.RUNNING:
            raise ValueError("Evaluation must be RUNNING")

        evaluation.state = EvaluationState.FAILED
        evaluation.finished = get_timestamp()
        self.update_evaluation(evaluation)
        return evaluation

    def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete a persisted evaluation."""
        self.read_evaluation(evaluation_id)
        self.store.delete_evaluation(evaluation_id)

    def delete_evaluations_for_scenario(self, scenario_id: str) -> None:
        """Remove all persisted evaluations for a scenario."""
        for evaluation in self.list_evaluations(scenario_id):
            try:
                self.store.delete_evaluation(evaluation.evaluation_id)
            except EntityDoesNotExist:
                pass

    # ───────────────────────────────────────────────────────────
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_evaluation(self, evaluation: Evaluation) -> None:
        """Persist an evaluation entity."""
        self.store.save_evaluation(evaluation.to_dict())

    def build_running_evaluation(
        self,
        evaluation_id: str,
        *,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        started: str | None = None,
    ) -> Evaluation:
        """Build a running evaluation without writing it to the store."""
        return Evaluation.create_default(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
            state=EvaluationState.RUNNING,
        )
