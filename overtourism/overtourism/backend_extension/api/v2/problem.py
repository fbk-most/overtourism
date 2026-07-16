# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.problem import (
    PostProblemData as BackendPostProblemData,
)
from overtourism.backend.api.v2.models.problem import (
    ProblemData as BackendProblemData,
)
from overtourism.backend.api.v2.models.problem import (
    UpdateProblemData as BackendUpdateProblemData,
)
from overtourism.backend.api.v2.problem import (
    create_problem as backend_create_problem,
)
from overtourism.backend.api.v2.problem import (
    delete_problem as backend_delete_problem,
)
from overtourism.backend.api.v2.problem import (
    list_problems as backend_list_problems,
)
from overtourism.backend.api.v2.problem import (
    read_problem as backend_read_problem,
)
from overtourism.backend.api.v2.problem import (
    update_problem as backend_update_problem,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)


class ProblemData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem_id: str
    version: int = 0
    tenant: str
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    objective: str | None = None
    groups: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    editable_indexes: list[str] = Field(default_factory=list)


class PostProblemData(BaseModel):
    name: str
    description: str
    objective: str | None = None
    groups: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class UpdateProblemData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int | None = None
    name: str | None = None
    description: str | None = None
    objective: str | None = None
    groups: list[str] | None = None
    links: list[str] | None = None


problem_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems",
    tags=["Problems"],
    dependencies=[Depends(get_auth_context)],
)


def _problem_payload(data: BaseModel) -> dict[str, Any]:
    payload = data.model_dump(exclude_unset=True)
    return {
        key: payload[key] for key in ("objective", "groups", "links") if key in payload
    }


def _problem_to_api(problem: BackendProblemData | dict[str, Any]) -> ProblemData:
    payload = problem.model_dump() if hasattr(problem, "model_dump") else dict(problem)
    extras = dict(payload.pop("extras", {}) or {})
    payload["objective"] = extras.get("objective")
    payload["groups"] = [str(item) for item in extras.get("groups", [])]
    payload["links"] = [str(item) for item in extras.get("links", [])]
    payload["editable_indexes"] = [
        str(item) for item in extras.get("editable_indexes", [])
    ]
    return ProblemData(**payload)


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
    try:
        return [
            _problem_to_api(problem)
            for problem in await backend_list_problems(tenant, handler=handler)
        ]
    except Exception as e:
        logger.error(f"Error listing problems: {e}")
        raise


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
    try:
        problem = await backend_create_problem(
            tenant,
            BackendPostProblemData(
                name=data.name,
                description=data.description,
                extras=_problem_payload(data),
            ),
            handler=handler,
        )
        return _problem_to_api(problem)
    except Exception as e:
        logger.error(f"Error creating problem {data.name}: {e}")
        raise


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
    try:
        problem = await backend_read_problem(tenant, problem_id, handler=handler)
        return _problem_to_api(problem)
    except Exception as e:
        logger.error(f"Error reading problem {problem_id}: {e}")
        raise


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
    try:
        problem = await backend_update_problem(
            tenant,
            problem_id,
            BackendUpdateProblemData(
                version=data.version,
                name=data.name,
                description=data.description,
                extras=_problem_payload(data),
            ),
            handler=handler,
        )
        return _problem_to_api(problem)
    except Exception as e:
        logger.error(f"Error updating problem {problem_id}: {e}")
        raise


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
    try:
        await backend_delete_problem(tenant, problem_id, handler=handler)
    except Exception as e:
        logger.error(f"Error deleting problem {problem_id}: {e}")
        raise
