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
    BASE_ROUTE,
    get_problem_or_404,
    get_widget_by_group,
    problem_from_model,
    problem_to_api,
    proposal_to_api,
    scenario_index_diffs,
    slugify_name,
)
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

problem_router = APIRouter(prefix=f"{BASE_ROUTE}/problems")


@problem_router.get(
    "",
    response_model=ProblemList,
    responses={
        500: {"description": "Problem manager error"},
        200: {"description": "Problem list"},
    },
)
async def list_problems(handler: Handler = Depends(get_handler)) -> ProblemList:
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
            proposal_to_api(handler, problem.problem_id, proposal)
            for proposal in handler.manager.list_proposals(problem.problem_id)
        ]
        return GetProblemData(**problem_to_api(problem), proposals=proposals)
    except Exception as e:
        logger.error(f"Error reading problem {problem.problem_id}: {e}")
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
        manager = handler.manager
        problem = get_problem_or_404(handler, problem_id)
        extras = dict(problem.extras)
        if data.editable_indexes is not None:
            extras["editable_indexes"] = data.editable_indexes
        if data.groups is not None:
            editable_indexes = get_widget_by_group(handler, data.groups)
            extras["editable_indexes"] = editable_indexes
            extras["groups"] = data.groups
        if data.objective is not None:
            extras["objective"] = data.objective
        if data.links is not None:
            extras["links"] = data.links

        manager.update_problem(
            problem_id,
            name=data.problem_name,
            description=data.problem_description,
            extras=extras,
        )

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
        manager = handler.manager
        problem = get_problem_or_404(handler, problem_id)
        models = [
            {
                "problem_id": problem.problem_id,
                "scenario_id": s.scenario_id,
                "scenario_name": s.name,
                "scenario_description": s.description,
                "created": s.created,
                "updated": s.updated,
                "index_diffs": scenario_index_diffs(handler, s),
                **s.extras,
            }
            for s in manager.list_scenarios(problem_id)
        ]
        return ScenarioList(scenarios=models)
    except Exception as e:
        logger.error(f"Error listing scenarios for problem {problem_id}: {e}")
        raise
