# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.shared.models.problem import (
    GetProblemData,
    PostProblemData,
    ProblemList,
    UpdateProblemData,
)
from overtourism.backend.api.shared.models.scenario import ScenarioList
from overtourism.backend.api.shared.utils import (
    get_problem_or_404,
    problem_from_model,
    problem_to_api,
    proposal_to_api,
    scenario_to_api,
    slugify_name,
)
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

problem_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems",
    dependencies=[Depends(get_auth_context)],
)


@problem_router.get(
    "",
    response_model=ProblemList,
    responses={
        500: {"description": "Problem manager error"},
        200: {"description": "Problem list"},
    },
)
async def list_problems(
    handler: Handler = Depends(get_handler),
) -> ProblemList:
    """List all problems in the current store."""
    try:
        problems = [
            {**problem_to_api(problem)} for problem in handler.manager.list_problems()
        ]
        return ProblemList(data=problems)
    except Exception as e:
        logger.error(f"Error listing problems: {e}")
        raise


@problem_router.post(
    "",
    response_model=dict,
    responses={
        500: {"description": "Problem manager error"},
        400: {"description": "Problem already exists"},
        200: {"description": "Problem created"},
    },
)
async def create_problem(
    data: PostProblemData,
    handler: Handler = Depends(get_handler),
) -> dict:
    """Create a new problem with default scenario."""
    try:
        problem_id = slugify_name(data.problem_name)
        handler.manager.create_problem(
            problem_id,
            problem_kwargs=problem_from_model(handler, data),
        )

        logger.info(f"Problem created: {problem_id}")
        return {"message": "Problem created successfully", "problem_id": problem_id}
    except Exception as e:
        logger.error(f"Error creating problem {data.problem_name}: {e}")
        raise


@problem_router.get(
    "/{problem_id}",
    response_model=GetProblemData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem details"},
    },
)
async def read_problem(
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> GetProblemData:
    """Read a problem together with its proposals."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        proposals = [
            proposal_to_api(handler, problem_id, proposal)
            for proposal in handler.manager.list_proposals(problem_id)
        ]
        return GetProblemData(**problem_to_api(problem), proposals=proposals)
    except Exception as e:
        logger.error(f"Error reading problem {problem_id}: {e}")
        raise


@problem_router.put(
    "/{problem_id}",
    response_model=dict,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Problem updated"},
    },
)
async def update_problem(
    problem_id: str,
    data: UpdateProblemData,
    handler: Handler = Depends(get_handler),
) -> dict:
    """Update a problem and persist the current aggregate."""
    try:
        get_problem_or_404(handler, problem_id)
        handler.manager.update_problem(problem_id, **problem_from_model(handler, data))

        logger.info(f"Problem updated: {problem_id}")
        return {"message": "Problem updated successfully"}
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
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> None:
    """Delete a problem from the store."""
    try:
        handler.manager.delete_problem(problem_id)
        logger.info(f"Problem deleted: {problem_id}")
    except Exception as e:
        logger.error(f"Error deleting problem {problem_id}: {e}")
        raise


@problem_router.get(
    "/{problem_id}/scenarios",
    response_model=ScenarioList,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Scenario models"},
    },
)
async def list_scenarios(
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> ScenarioList:
    """List all scenarios for a problem."""
    try:
        get_problem_or_404(handler, problem_id)
        scenarios = [
            scenario_to_api(handler, s)
            for s in handler.manager.list_scenarios(problem_id)
        ]
        return ScenarioList(scenarios=scenarios)
    except Exception as e:
        logger.error(f"Error listing scenarios for problem {problem_id}: {e}")
        raise
