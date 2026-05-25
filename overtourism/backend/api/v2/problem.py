# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from slugify import slugify

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.problem import (
    PostProblemData,
    ProblemData,
    UpdateProblemData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_problem_or_404,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

problem_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems",
    dependencies=[Depends(get_auth_context)],
)


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
    """List all problems in the current store."""
    try:
        return [
            problem.to_dict()
            for problem in handler.manager.list_problems()
            if problem.tenant == tenant
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
    """Create a new problem with default scenario."""
    try:
        problem_payload = data.model_dump(exclude_unset=True)
        groups = problem_payload.get("groups", [])
        extras = handler.manager.problem_extras_from_dict(problem_payload)
        extras["editable_indexes"] = (
            handler.viewer.get_widget_ids_by_groups(groups)
            if handler.viewer is not None and groups
            else []
        )
        problem_id = slugify(data.problem_name)
        handler.manager.create_problem(
            problem_id,
            problem_kwargs={
                "name": data.problem_name,
                "description": data.problem_description,
                "extras": extras,
                "tenant": tenant,
            },
        )
        problem = handler.manager.read_problem(problem_id)
        logger.info(f"Problem created: {problem_id}")
        return problem.to_dict()
    except Exception as e:
        logger.error(f"Error creating problem {data.problem_name}: {e}")
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
    """Read a problem."""
    try:
        problem = get_problem_or_404(handler, tenant, problem_id)
        return problem.to_dict()
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
    """Update a problem and persist the current aggregate."""
    try:
        problem = get_problem_or_404(handler, tenant, problem_id)
        check_version(problem.version, data.version)
        problem_payload = data.model_dump(exclude_unset=True, exclude={"version"})
        groups = problem_payload.get("groups", [])
        extras = handler.manager.problem_extras_from_dict(problem_payload)
        extras["editable_indexes"] = (
            handler.viewer.get_widget_ids_by_groups(groups)
            if handler.viewer is not None and groups
            else []
        )
        handler.manager.update_problem(
            problem_id,
            name=data.problem_name,
            description=data.problem_description,
            extras=extras,
        )
        updated_problem = handler.manager.read_problem(problem_id)
        logger.info(f"Problem updated: {problem_id}")
        return updated_problem.to_dict()
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
    """Delete a problem from the store."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        handler.manager.delete_problem(problem_id)
        logger.info(f"Problem deleted: {problem_id}")
    except Exception as e:
        logger.error(f"Error deleting problem {problem_id}: {e}")
        raise
