# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from overtourism.dt_manager.utils.dictable import Dictable
from overtourism.dt_manager.utils.utils import get_timestamp

DEFAULT_EVALUATION_TYPE = "default"


class EvaluationState(StrEnum):
    """Lifecycle states for an evaluation."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Evaluation(Dictable):
    """Domain entity for a scenario evaluation.

    The evaluation type is intentionally kept as a domain-specific string so
    backend adapters can define their own result families without forcing a
    shared enum in dt_manager.
    """

    evaluation_id: str
    scenario_id: str
    session_id: str | None = None
    type: str = DEFAULT_EVALUATION_TYPE
    version: int = 0
    state: EvaluationState = EvaluationState.RUNNING
    started: str | None = None
    finished: str | None = None
    result: dict | None = None

    @classmethod
    def create_default(
        cls,
        evaluation_id: str,
        scenario_id: str,
        *,
        type: str = DEFAULT_EVALUATION_TYPE,
        version: int = 1,
        state: EvaluationState = EvaluationState.RUNNING,
        started: str | None = None,
        finished: str | None = None,
        result: dict | None = None,
    ) -> Evaluation:
        """Create a new evaluation with default timestamps."""
        return cls(
            evaluation_id=evaluation_id,
            scenario_id=scenario_id,
            session_id=None,
            type=type,
            version=version,
            state=state,
            started=get_timestamp() if started is None else started,
            finished=finished,
            result=result,
        )

    @classmethod
    def from_dict(cls, evaluation_dict: dict[str, Any]) -> Evaluation:
        """Build an evaluation from a flat dictionary payload."""
        state = evaluation_dict.get("state", EvaluationState.RUNNING)
        if not isinstance(state, EvaluationState):
            state = EvaluationState(state)
        return cls(
            evaluation_id=evaluation_dict["evaluation_id"],
            scenario_id=evaluation_dict["scenario_id"],
            session_id=evaluation_dict.get("session_id"),
            type=evaluation_dict.get("type", DEFAULT_EVALUATION_TYPE),
            version=evaluation_dict.get("version", 0),
            state=state,
            started=evaluation_dict.get("started"),
            finished=evaluation_dict.get("finished"),
            result=evaluation_dict.get("result"),
        )
