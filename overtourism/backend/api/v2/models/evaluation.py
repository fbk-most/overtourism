# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    EvaluationState,
)


class EvaluationData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    evaluation_id: str
    scenario_id: str
    type: str = DEFAULT_EVALUATION_TYPE
    version: int = 1
    state: EvaluationState = EvaluationState.RUNNING
    started: str | None = None
    finished: str | None = None
    result: dict[str, Any] | None = None


class EvaluationOutputData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    scenario_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class PostEvaluationData(BaseModel):
    scenario_id: str


class UpdateEvaluationData(BaseModel):
    ensemble_size: int = 20
    kwargs: dict[str, Any] = Field(default_factory=dict)
