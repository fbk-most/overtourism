# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import Field

from overtourism.backend.api.models.problem import (
    PostProblemData,
    ProblemData,
    UpdateProblemData,
)


class OvertourismProblemData(ProblemData):
    objective: str | None = None
    groups: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    editable_indexes: list[str] = Field(default_factory=list)


class OvertourismPostProblemData(PostProblemData):
    objective: str | None = None
    groups: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class OvertourismUpdateProblemData(UpdateProblemData):
    objective: str | None = None
    groups: list[str] | None = None
    links: list[str] | None = None
