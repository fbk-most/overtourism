# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from overtourism.dt_manager.classes.dictable import Dictable
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.classes.model import ModelOutput

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
    type: str
    version: int = 0
    state: EvaluationState = EvaluationState.RUNNING
    started: str | None = None
    finished: str | None = None
    result: ModelOutput | dict | None = None

    @classmethod
    def create_default(
        cls,
        evaluation_id: str,
        *,
        scenario_id: str,
        type: str,
        version: int = 0,
        state: EvaluationState = EvaluationState.RUNNING,
        started: str | None = None,
        finished: str | None = None,
        result: ModelOutput | dict | None = None,
    ) -> Evaluation:
        """Create a new evaluation with default timestamps."""
        return cls(
            evaluation_id=evaluation_id,
            scenario_id=scenario_id,
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
            type=evaluation_dict["type"],
            version=evaluation_dict.get("version", 0),
            state=state,
            started=evaluation_dict.get("started"),
            finished=evaluation_dict.get("finished"),
            result=evaluation_dict.get("result"),
        )
