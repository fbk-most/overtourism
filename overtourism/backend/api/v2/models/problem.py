# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostProblemData(BaseModel):
    problem_name: str
    problem_description: str
    extras: dict[str, Any] = Field(default_factory=dict)


class UpdateProblemData(BaseModel):
    problem_name: str | None = None
    problem_description: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class ProblemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    version: int = 1
    tenant: str
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
