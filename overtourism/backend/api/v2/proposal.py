# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from overtourism.backend.api.models.proposal import (
    PostProposalData,
    ProposalData,
    UpdateProposalData,
)
from overtourism.backend.api.utils.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.utils.dependencies import get_handler
from overtourism.backend.api.utils.utils import (
    check_version,
    get_proposal_or_404,
    proposal_to_api,
    validate_related_scenario_ids,
)
from overtourism.backend.auth.dependencies import Handler, get_auth_context

logger = logging.getLogger(__name__)

proposal_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/proposals",
    tags=["Proposals"],
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
    problem_id: str | None = None,
    scenario_id: str | None = None,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> list[ProposalData]:
    """List all proposals for a problem."""
    try:
        proposals = handler.manager.list_proposals(
            problem_id=problem_id,
            scenario_id=scenario_id,
            tenant=tenant,
        )
        return [proposal_to_api(handler, proposal) for proposal in proposals]
    except Exception as e:
        logger.error(f"Error listing proposals: {e}")
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
    data: PostProposalData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ProposalData:
    """Create a proposal for a problem."""
    try:
        proposal_payload = data.model_dump(exclude_unset=True)
        proposal_payload["related_scenario_ids"] = validate_related_scenario_ids(
            tenant,
            handler,
            proposal_payload.get("related_scenario_ids"),
        )
        proposal = handler.manager.create_proposal(**proposal_payload)
        logger.info(f"Proposal created: {proposal.proposal_id}")
        return proposal_to_api(handler, proposal)
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
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
    proposal_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ProposalData:
    """Read a proposal by identifier."""
    try:
        proposal = get_proposal_or_404(tenant, handler, proposal_id)
        return proposal_to_api(handler, proposal)
    except Exception as e:
        logger.error(f"Error reading proposal {proposal_id}: {e}")
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
    proposal_id: str,
    data: UpdateProposalData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ProposalData:
    """Update a proposal and its related scenario links."""
    try:
        current_proposal = get_proposal_or_404(tenant, handler, proposal_id)
        check_version(current_proposal.version, data.version)
        proposal_payload = data.model_dump(exclude_unset=True, exclude={"version"})
        proposal_payload["related_scenario_ids"] = validate_related_scenario_ids(
            tenant,
            handler,
            proposal_payload.get("related_scenario_ids"),
        )
        handler.manager.update_proposal(proposal_id, **proposal_payload)
        updated_proposal = handler.manager.read_proposal(proposal_id)
        logger.info(f"Proposal updated: {proposal_id}")
        return proposal_to_api(handler, updated_proposal)
    except Exception as e:
        logger.error(f"Error updating proposal {proposal_id}: {e}")
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
    proposal_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> None:
    """Delete a proposal from a problem."""
    try:
        get_proposal_or_404(tenant, handler, proposal_id)
        handler.manager.delete_proposal(proposal_id)
        logger.info(f"Proposal deleted: {proposal_id}")
    except Exception as e:
        logger.error(f"Error deleting proposal {proposal_id}: {e}")
        raise
