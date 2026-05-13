# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.shared.models.problem import Proposal, ProposalList
from overtourism.backend.api.shared.utils import (
    BASE_ROUTE,
    get_problem_or_404,
    parse_proposal_model,
    proposal_to_api,
)
from overtourism.backend.handler import Handler

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
    handler: Handler = Depends(get_handler),
) -> ProposalList:
    """List all proposals for a problem."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        p_list = [
            Proposal(**proposal_to_api(handler, problem.problem_id, proposal))
            for proposal in handler.manager.list_proposals(problem.problem_id)
        ]
        return ProposalList(data=p_list)
    except Exception as e:
        logger.error(f"Error listing proposals for problem {problem.problem_id}: {e}")
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
    handler: Handler = Depends(get_handler),
) -> dict:
    """Create a proposal for a problem."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        proposal_id = handler.manager.create_proposal(
            problem.problem_id,
            **parse_proposal_model(handler, proposal),
        )

        logger.info(f"Proposal created: {proposal_id} for problem {problem.problem_id}")
        return {"message": "Proposal created successfully", "proposal_id": proposal_id}
    except Exception as e:
        logger.error(f"Error creating proposal for problem {problem.problem_id}: {e}")
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
    handler: Handler = Depends(get_handler),
) -> Proposal:
    """Read a proposal by identifier."""
    try:
        proposal = handler.manager.read_proposal(problem_id, proposal_id)
        return Proposal(**proposal_to_api(handler, problem_id, proposal))
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
    handler: Handler = Depends(get_handler),
) -> dict:
    """Update a proposal and its related scenario links."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        handler.manager.update_proposal(
            problem.problem_id,
            proposal_id,
            **parse_proposal_model(handler, proposal),
        )
        logger.info(f"Proposal updated: {proposal_id} for problem {problem.problem_id}")
        return {"message": "Proposal updated successfully"}
    except Exception as e:
        logger.error(
            f"Error updating proposal {proposal_id} for problem {problem.problem_id}: {e}"
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
    handler: Handler = Depends(get_handler),
) -> None:
    """Delete a proposal from a problem."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        handler.manager.delete_proposal(problem.problem_id, proposal_id)
        logger.info(f"Proposal deleted: {proposal_id} for problem {problem.problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting proposal {proposal_id} for problem {problem.problem_id}: {e}"
        )
        raise
