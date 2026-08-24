# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from overtourism.backend.api.models.evaluation import EvaluationData
from overtourism.backend.api.models.scenario import ScenarioData


class CreateSessionData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionSummaryData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    owner_id: str | None = None
    created: str
    updated: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    active_scenario_id: str | None = None
    draft_ids: list[str] = Field(default_factory=list)


class SessionData(SessionSummaryData):
    drafts: list[ScenarioData] = Field(default_factory=list)
    evaluations: dict[str, EvaluationData] = Field(default_factory=dict)
