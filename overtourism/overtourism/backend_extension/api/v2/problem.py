# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.utils.dependencies import get_handler
from overtourism.backend.api.v2.problem import (
    create_problem as base_create_problem,
)
from overtourism.backend.api.v2.problem import (
    delete_problem as base_delete_problem,
)
from overtourism.backend.api.v2.problem import (
    list_problems as base_list_problems,
)
from overtourism.backend.api.v2.problem import (
    read_problem as base_read_problem,
)
from overtourism.backend.api.v2.problem import (
    update_problem as base_update_problem,
)
from overtourism.backend.auth.dependencies import Handler, get_auth_context
from overtourism.overtourism.backend_extension.api.models.problem import (
    OvertourismPostProblemData,
    OvertourismProblemData,
    OvertourismUpdateProblemData,
)
from overtourism.overtourism.backend_extension.api.utils.utils import (
    prepare_problem_payload,
    to_problem_api_overtourism,
)

logger = logging.getLogger(__name__)


problem_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems",
    tags=["Problems"],
    dependencies=[Depends(get_auth_context)],
)


@problem_router.get(
    "",
    response_model=list[OvertourismProblemData],
    responses={
        500: {"description": "Problem manager error"},
        200: {"description": "Problem list"},
    },
)
async def list_problems(
    tenant: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> list[OvertourismProblemData]:
    try:
        listed = await base_list_problems(tenant=tenant, handler=handler)
        return [to_problem_api_overtourism(problem) for problem in listed]
    except Exception as e:
        logger.error(f"Error listing problems: {e}")
        raise


@problem_router.post(
    "",
    response_model=OvertourismProblemData,
    responses={
        500: {"description": "Problem manager error"},
        400: {"description": "Problem already exists"},
        200: {"description": "Problem created"},
    },
)
async def create_problem(
    tenant: str,
    data: OvertourismPostProblemData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProblemData:
    try:
        payload = prepare_problem_payload(
            problem_id=None,
            tenant=tenant,
            payload=data.model_dump(),
            handler=handler,
        )
        created = await base_create_problem(
            tenant=tenant,
            data=payload,
            handler=handler,
        )
        return to_problem_api_overtourism(created)
    except Exception as e:
        logger.error(f"Error creating problem {data.name}: {e}")
        raise


@problem_router.get(
    "/{problem_id}",
    response_model=OvertourismProblemData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem details"},
    },
)
async def read_problem(
    tenant: str,
    problem_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProblemData:
    try:
        read = await base_read_problem(tenant, problem_id, handler=handler)
        return to_problem_api_overtourism(read)
    except Exception as e:
        logger.error(f"Error reading problem {problem_id}: {e}")
        raise


@problem_router.put(
    "/{problem_id}",
    response_model=OvertourismProblemData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem updated"},
    },
)
async def update_problem(
    tenant: str,
    problem_id: str,
    data: OvertourismUpdateProblemData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProblemData:
    try:
        payload = prepare_problem_payload(
            problem_id=problem_id,
            tenant=tenant,
            payload=data.model_dump(exclude_unset=True),
            handler=handler,
        )
        updated = await base_update_problem(
            tenant=tenant,
            problem_id=problem_id,
            data=payload,
            handler=handler,
        )
        return to_problem_api_overtourism(updated)
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
    handler: Annotated[Handler, Depends(get_handler)],
) -> None:
    try:
        await base_delete_problem(tenant, problem_id, handler=handler)
    except Exception as e:
        logger.error(f"Error deleting problem {problem_id}: {e}")
        raise
