# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    EvaluationState,
)


class EvaluationData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    evaluation_id: str
    scenario_id: str
    type: str = DEFAULT_EVALUATION_TYPE
    version: int = 0
    state: EvaluationState = EvaluationState.RUNNING
    started: str | None = None
    finished: str | None = None

    @classmethod
    def from_domain(cls, evaluation: Any) -> "EvaluationData":
        payload = evaluation.to_dict() if hasattr(evaluation, "to_dict") else evaluation
        return cls(
            evaluation_id=payload["evaluation_id"],
            scenario_id=payload["scenario_id"],
            type=payload.get("type", DEFAULT_EVALUATION_TYPE),
            version=payload.get("version", 0),
            state=payload.get("state", EvaluationState.RUNNING),
            started=payload.get("started"),
            finished=payload.get("finished"),
        )


class EvaluationOutputData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem_id: str
    scenario_id: str
    evaluation_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class PostEvaluationData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: str
    ensemble_size: int = 20
    kwargs: dict[str, Any] = Field(default_factory=dict)


class UpdateEvaluationData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int | None = None
    ensemble_size: int = 20
    kwargs: dict[str, Any] = Field(default_factory=dict)
