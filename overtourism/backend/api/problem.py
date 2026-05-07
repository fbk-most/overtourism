# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import slugify
from fastapi import APIRouter, Depends

from overtourism.backend.api.dependencies import get_managers
from overtourism.backend.api.utils import (
    apply_problem_request_to_metadata,
    build_problem_extras,
    build_proposal_extras,
    extract_related_scenario_ids,
    get_problem_or_404,
    get_widget_by_group,
    problem_to_api,
    proposal_to_api,
)
from overtourism.backend.managers import Managers
from overtourism.backend.shared.models.problem import (
    GetProblemData,
    PostProblemData,
    ProblemList,
    UpdateProblemData,
)
from overtourism.backend.shared.models.scenario import ScenarioList
from overtourism.backend.shared.utils import BASE_ROUTE, get_timestamp

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
async def list_problems(mgrs: Managers = Depends(get_managers)) -> ProblemList:
    """List all problems in the current store."""
    try:
        manager = mgrs.manager
        problems = [
            {
                "problem_id": problem.problem_id,
                **problem_to_api(problem),
            }
            for problem in (manager.get_problem(pid) for pid in manager.list_problems())
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
    mgrs: Managers = Depends(get_managers),
) -> dict:
    """Create a new problem with its default scenario and proposals."""
    try:
        manager = mgrs.manager
        problem_id = slugify.slugify(data.problem_name)
        timestamp = get_timestamp()

        editable_indexes = get_widget_by_group(mgrs, data.groups)

        extras = build_problem_extras(mgrs, data.model_dump(), editable_indexes)

        manager.add_problem(
            problem_id=problem_id,
            name=data.problem_name,
            description=data.problem_description,
            created=timestamp,
            updated=timestamp,
            extras=extras,
        )
        manager.save_problem(problem_id)
        manager.add_scenario(
            problem_id,
            "model_0",
            name="Base",
            description="Scenario base",
        )
        manager.save_scenario(problem_id, "model_0")
        manager.evaluate_scenario(problem_id, "model_0")

        # Create initial proposals
        for i, p in enumerate(data.proposals):
            p_data = p if isinstance(p, dict) else p.model_dump(exclude_unset=True)
            proposal_extras = build_proposal_extras(mgrs, p_data)
            related_scenario_ids = extract_related_scenario_ids(p_data)
            manager.add_proposal(
                problem_id,
                proposal_id=f"proposal_{i}",
                name=p_data.get("proposal_title"),
                description=p_data.get("proposal_description"),
                status=p_data.get("status", "draft"),
                extras=proposal_extras,
            )
            if related_scenario_ids:
                manager.set_related_scenario_ids_for_proposal(
                    problem_id,
                    f"proposal_{i}",
                    related_scenario_ids,
                )
            manager.save_proposal(problem_id, f"proposal_{i}")

        manager.save_problem(problem_id)

        logger.info(f"Problem created: {problem_id}")
        return {"message": "Problem created successfully", "problem_id": problem_id}
    except Exception as e:
        logger.error(f"Error creating problem {data.problem_name}: {e}")
        raise


@problem_router.put(
    "/refresh",
    responses={
        500: {"description": "Problem manager error"},
        200: {"description": "Problem refreshed"},
    },
)
async def refresh_problems(mgrs: Managers = Depends(get_managers)) -> None:
    """Reload all problems from storage."""
    try:
        mgrs.manager.load_problems()
    except Exception as e:
        logger.error(f"Error refreshing problems: {e}")
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
    mgrs: Managers = Depends(get_managers),
) -> GetProblemData:
    """Read a problem together with its proposals."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)
        scenario_manager = manager.get_scenario_manager(problem_id)
        proposal_manager = manager.get_proposal_manager(problem_id)
        proposals = [
            proposal_to_api(
                proposal,
                manager.get_related_scenario_ids_for_proposal(problem_id, pid),
                scenario_manager.scenarios,
            )
            for pid, proposal in proposal_manager.proposals.items()
        ]
        return GetProblemData(
            problem_id=problem.problem_id,
            proposals=proposals,
            **problem_to_api(problem),
        )
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
    mgrs: Managers = Depends(get_managers),
) -> dict:
    """Update a problem and persist the current aggregate."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)
        problem.updated = get_timestamp()
        apply_problem_request_to_metadata(mgrs, problem, data.model_dump())

        manager.save_problem(problem_id)

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
    mgrs: Managers = Depends(get_managers),
) -> None:
    """Delete a problem from the store."""
    try:
        mgrs.manager.delete_problem(problem_id)
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
    mgrs: Managers = Depends(get_managers),
) -> ScenarioList:
    """List all scenarios for a problem."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)
        scenario_manager = manager.get_scenario_manager(problem_id)
        models = [
            {
                "problem_id": problem.problem_id,
                "scenario_id": s.scenario_id,
                "scenario_name": s.name,
                "scenario_description": s.description,
                "created": s.created,
                "updated": s.updated,
                "index_diffs": s.index_diffs,
                **s.extras,
            }
            for s in scenario_manager.scenarios.values()
        ]
        return ScenarioList(scenarios=models)
    except Exception as e:
        logger.error(f"Error listing scenarios for problem {problem_id}: {e}")
        raise
