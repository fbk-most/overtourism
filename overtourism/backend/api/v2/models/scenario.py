# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioData(BaseModel):
    model_config = ConfigDict(extra="allow")

    problem_id: str
    scenario_id: str
    scenario_name: str
    scenario_description: str
    created: str
    updated: str
    index_diffs: dict[str, str]


class ScenarioList(BaseModel):
    scenarios: list[ScenarioData]


class InputEvaluationData(BaseModel):
    ensemble_size: int = 20
    values: dict[str, list[int | float] | int | float] = Field(default_factory=dict)


class SaveData(BaseModel):
    model_config = ConfigDict(extra="allow")

    scenario_name: str
    scenario_description: str
    values: dict[str, Any] = Field(default_factory=dict)


class OutputData(BaseModel):
    problem_id: str
    scenario_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    index_diffs: dict[str, str] = Field(default_factory=dict)
    widgets: dict | None = None
    editable_indexes: list[str] | None = None
