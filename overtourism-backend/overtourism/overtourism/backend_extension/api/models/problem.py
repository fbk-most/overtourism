# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.api.models.problem import (
    PostProblemData,
    ProblemData,
    UpdateProblemData,
)
from pydantic import Field


class OvertourismProblemData(ProblemData):
    objective: str | None = None
    links: list[str] = Field(default_factory=list)


class OvertourismPostProblemData(PostProblemData):
    objective: str | None = None
    links: list[str] = Field(default_factory=list)


class OvertourismUpdateProblemData(UpdateProblemData):
    objective: str | None = None
    links: list[str] | None = None
