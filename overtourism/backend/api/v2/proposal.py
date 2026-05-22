# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Response

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.proposal import (
    PostProposalData,
    ProposalData,
    UpdateProposalData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_problem_or_404,
    get_proposal_or_404,
    set_version_header,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

proposal_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/proposals",
    dependencies=[Depends(get_auth_context)],
)


@proposal_router.get(
    "",
    response_model=list[ProposalData],
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Proposal list"},
    },
)
async def list_proposals(
    tenant: str,
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> list[ProposalData]:
    """List all proposals for a problem."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        return [
            proposal.to_dict()
            for proposal in handler.manager.list_proposals(problem_id)
        ]
    except Exception as e:
        logger.error(f"Error listing proposals for problem {problem_id}: {e}")
        raise


@proposal_router.post(
    "",
    response_model=ProposalData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Proposal created"},
    },
)
async def create_proposal(
    tenant: str,
    problem_id: str,
    proposal: PostProposalData,
    response: Response,
    handler: Handler = Depends(get_handler),
) -> ProposalData:
    """Create a proposal for a problem."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        proposal_id = handler.manager.create_proposal(
            problem_id,
            **proposal.model_dump(exclude_unset=True),
        ).proposal_id
        proposal_entity = handler.manager.read_proposal(problem_id, proposal_id)
        set_version_header(response, proposal_entity.version)
        logger.info(f"Proposal created: {proposal_id} for problem {problem_id}")
        return proposal_entity.to_dict()
    except Exception as e:
        logger.error(f"Error creating proposal for problem {problem_id}: {e}")
        raise


@proposal_router.get(
    "/{proposal_id}",
    response_model=ProposalData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal details"},
    },
)
async def read_proposal(
    tenant: str,
    problem_id: str,
    proposal_id: str,
    response: Response,
    handler: Handler = Depends(get_handler),
) -> ProposalData:
    """Read a proposal by identifier."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        proposal = get_proposal_or_404(handler, problem_id, proposal_id)
        set_version_header(response, proposal.version)
        return proposal.to_dict()
    except Exception as e:
        logger.error(
            f"Error reading proposal {proposal_id} for problem {problem_id}: {e}"
        )
        raise


@proposal_router.put(
    "/{proposal_id}",
    response_model=ProposalData,
    responses={
        500: {"description": "Problem manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal updated"},
    },
)
async def update_proposal(
    tenant: str,
    problem_id: str,
    proposal_id: str,
    proposal: UpdateProposalData,
    response: Response,
    *,
    version: str | None = Header(default=None, alias="Version"),
    handler: Handler = Depends(get_handler),
) -> ProposalData:
    """Update a proposal and its related scenario links."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current_proposal = get_proposal_or_404(handler, problem_id, proposal_id)
        check_version(current_proposal.version, version)
        handler.manager.update_proposal(
            problem_id,
            proposal_id,
            **proposal.model_dump(exclude_unset=True),
        )
        updated_proposal = handler.manager.read_proposal(problem_id, proposal_id)
        set_version_header(response, updated_proposal.version)
        logger.info(f"Proposal updated: {proposal_id} for problem {problem_id}")
        return updated_proposal.to_dict()
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
    tenant: str,
    problem_id: str,
    proposal_id: str,
    version: str | None = Header(default=None, alias="Version"),
    handler: Handler = Depends(get_handler),
) -> None:
    """Delete a proposal from a problem."""
    try:
        get_problem_or_404(handler, tenant, problem_id)
        proposal = get_proposal_or_404(handler, problem_id, proposal_id)
        check_version(proposal.version, version)
        handler.manager.delete_proposal(problem_id, proposal_id)
        logger.info(f"Proposal deleted: {proposal_id} for problem {problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting proposal {proposal_id} for problem {problem_id}: {e}"
        )
        raise
