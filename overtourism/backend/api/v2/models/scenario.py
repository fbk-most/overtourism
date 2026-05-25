# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    scenario_id: str
    version: int = 0
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
    index_values: list[dict[str, Any]] = Field(default_factory=list)


class PostScenarioData(BaseModel):
    base_scenario_id: str
    name: str | None = None
    description: str | None = None
    values: dict[str, Any] | None = None
    extras: dict[str, Any] | None = None


class SaveScenarioData(BaseModel):
    model_config = ConfigDict(extra="forbid", exclude_none=True)

    version: int | None = None
    name: str | None = None
    description: str | None = None
    extras: dict[str, Any] | None = None
    proposal_id: str | None = None


class UpdateScenarioData(BaseModel):
    model_config = ConfigDict(extra="forbid", exclude_none=True)

    version: int | None = None
    name: str | None = None
    description: str | None = None
    values: dict[str, Any] | None = None
    extras: dict[str, Any] | None = None
