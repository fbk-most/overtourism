# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.dependencies import get_managers
from overtourism.backend.api.utils import (
    get_problem_or_404,
    parse_proposal_request,
    proposal_to_api,
)
from overtourism.backend.managers import Managers
from overtourism.backend.shared.models.problem import Proposal, ProposalList
from overtourism.backend.shared.utils import BASE_ROUTE

logger = logging.getLogger(__name__)

proposal_router = APIRouter(prefix=f"{BASE_ROUTE}/proposals")


@proposal_router.get(
    "",
    response_model=ProposalList,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Proposal list"},
    },
)
async def list_proposals(
    problem_id: str,
    mgrs: Managers = Depends(get_managers),
) -> ProposalList:
    """List all proposals for a problem."""
    try:
        manager = mgrs.manager
        get_problem_or_404(mgrs, problem_id)
        scenario_map = {
            scenario.scenario_id: scenario
            for scenario in manager.list_scenarios(problem_id)
        }
        p_list = [
            Proposal(
                **proposal_to_api(
                    proposal,
                    manager.get_related_scenario_ids_for_proposal(
                        problem_id, proposal.proposal_id
                    ),
                    scenario_map,
                    mgrs,
                )
            )
            for proposal in manager.list_proposals(problem_id)
        ]
        return ProposalList(data=p_list)
    except Exception as e:
        logger.error(f"Error listing proposals for problem {problem_id}: {e}")
        raise


@proposal_router.post(
    "",
    response_model=dict,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Proposal created"},
    },
)
async def create_proposal(
    problem_id: str,
    proposal: Proposal,
    mgrs: Managers = Depends(get_managers),
) -> dict:
    """Create a proposal for a problem."""
    try:
        manager = mgrs.manager
        get_problem_or_404(mgrs, problem_id)

        p_data = proposal.model_dump(exclude_unset=True)
        extras, scenario_ids = parse_proposal_request(mgrs, p_data)
        related_scenarios = p_data.get("related_scenarios")

        proposal_id = manager.create_proposal(
            problem_id,
            name=p_data.get("proposal_title"),
            description=p_data.get("proposal_description"),
            status=p_data.get("status", "draft"),
            extras=extras,
            related_scenario_ids=scenario_ids
            if related_scenarios is not None
            else None,
        )

        logger.info(f"Proposal created: {proposal_id} for problem {problem_id}")
        return {"message": "Proposal created successfully", "proposal_id": proposal_id}
    except Exception as e:
        logger.error(f"Error creating proposal for problem {problem_id}: {e}")
        raise


@proposal_router.get(
    "/{proposal_id}",
    response_model=Proposal,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal details"},
    },
)
async def read_proposal(
    problem_id: str,
    proposal_id: str,
    mgrs: Managers = Depends(get_managers),
) -> Proposal:
    """Read a proposal by identifier."""
    try:
        manager = mgrs.manager
        proposal = manager.read_proposal(problem_id, proposal_id)
        scenario_map = {
            scenario.scenario_id: scenario
            for scenario in manager.list_scenarios(problem_id)
        }
        return Proposal(
            **proposal_to_api(
                proposal,
                manager.get_related_scenario_ids_for_proposal(problem_id, proposal_id),
                scenario_map,
                mgrs,
            )
        )
    except Exception as e:
        logger.error(
            f"Error reading proposal {proposal_id} for problem {problem_id}: {e}"
        )
        raise


@proposal_router.put(
    "/{proposal_id}",
    response_model=dict,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal updated"},
    },
)
async def update_proposal(
    problem_id: str,
    proposal_id: str,
    proposal: Proposal,
    mgrs: Managers = Depends(get_managers),
) -> dict:
    """Update a proposal and its related scenario links."""
    try:
        get_problem_or_404(mgrs, problem_id)

        p_data = proposal.model_dump(exclude_unset=True)
        extras, scenario_ids = parse_proposal_request(mgrs, p_data)

        mgrs.manager.update_proposal(
            problem_id,
            proposal_id,
            name=p_data.get("proposal_title"),
            description=p_data.get("proposal_description"),
            status=p_data.get("status"),
            extras=extras if extras else None,
            related_scenario_ids=scenario_ids,
        )
        logger.info(f"Proposal updated: {proposal_id} for problem {problem_id}")
        return {"message": "Proposal updated successfully"}
    except Exception as e:
        logger.error(
            f"Error updating proposal {proposal_id} for problem {problem_id}: {e}"
        )
        raise


@proposal_router.delete(
    "/{proposal_id}",
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Proposal deleted"},
    },
)
async def delete_proposal(
    problem_id: str,
    proposal_id: str,
    mgrs: Managers = Depends(get_managers),
) -> None:
    """Delete a proposal from a problem."""
    try:
        manager = mgrs.manager
        get_problem_or_404(mgrs, problem_id)
        manager.delete_proposal(problem_id, proposal_id)
        logger.info(f"Proposal deleted: {proposal_id} for problem {problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting proposal {proposal_id} for problem {problem_id}: {e}"
        )
        raise
