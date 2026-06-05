# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostProblemData(BaseModel):
    name: str
    description: str
    extras: dict[str, Any] = Field(default_factory=dict)


class UpdateProblemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = None
    name: str | None = None
    description: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class ProblemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    version: int = 0
    tenant: str
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
