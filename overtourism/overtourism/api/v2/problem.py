# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.problem import (
    PostProblemData as BackendPostProblemData,
)
from overtourism.backend.api.v2.models.problem import ProblemData
from overtourism.backend.api.v2.models.problem import (
    UpdateProblemData as BackendUpdateProblemData,
)
from overtourism.backend.api.v2.problem import create_problem as create_problem_generic
from overtourism.backend.api.v2.problem import delete_problem as delete_problem_generic
from overtourism.backend.api.v2.problem import list_problems as list_problems_generic
from overtourism.backend.api.v2.problem import read_problem as read_problem_generic
from overtourism.backend.api.v2.problem import update_problem as update_problem_generic
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

problem_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems",
    dependencies=[Depends(get_auth_context)],
)


class PostProblemData(BaseModel):
    problem_name: str
    problem_description: str
    objective: str | None = None
    groups: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    def to_backend(self) -> BackendPostProblemData:
        return BackendPostProblemData(
            problem_name=self.problem_name,
            problem_description=self.problem_description,
            extras=_problem_extras(self),
        )


class UpdateProblemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = None
    problem_name: str | None = None
    problem_description: str | None = None
    objective: str | None = None
    groups: list[str] | None = None
    links: list[str] | None = None

    def to_backend(self) -> BackendUpdateProblemData:
        return BackendUpdateProblemData(
            version=self.version,
            problem_name=self.problem_name,
            problem_description=self.problem_description,
            extras=_problem_extras(self),
        )


def _problem_extras(data: Any) -> dict[str, Any]:
    payload = data.model_dump(exclude_unset=True)
    return {
        key: payload[key] for key in ("objective", "groups", "links") if key in payload
    }


@problem_router.get(
    "",
    response_model=list[ProblemData],
    responses={
        500: {"description": "Problem manager error"},
        200: {"description": "Problem list"},
    },
)
async def list_problems(
    tenant: str,
    handler: Handler = Depends(get_handler),
) -> list[ProblemData]:
    return await list_problems_generic(tenant, handler)


@problem_router.post(
    "",
    response_model=ProblemData,
    responses={
        500: {"description": "Problem manager error"},
        400: {"description": "Problem already exists"},
        200: {"description": "Problem created"},
    },
)
async def create_problem(
    tenant: str,
    data: PostProblemData,
    handler: Handler = Depends(get_handler),
) -> ProblemData:
    return await create_problem_generic(tenant, data.to_backend(), handler)


@problem_router.get(
    "/{problem_id}",
    response_model=ProblemData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem details"},
    },
)
async def read_problem(
    tenant: str,
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> ProblemData:
    return await read_problem_generic(tenant, problem_id, handler)


@problem_router.put(
    "/{problem_id}",
    response_model=ProblemData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem updated"},
    },
)
async def update_problem(
    tenant: str,
    problem_id: str,
    data: UpdateProblemData,
    handler: Handler = Depends(get_handler),
) -> ProblemData:
    return await update_problem_generic(tenant, problem_id, data.to_backend(), handler)


@problem_router.delete(
    "/{problem_id}",
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem deleted"},
    },
)
async def delete_problem(
    tenant: str,
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> None:
    await delete_problem_generic(tenant, problem_id, handler)
