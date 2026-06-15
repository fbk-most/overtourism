# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import typing

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.proposal import (
    PostProposalData,
    ProposalData,
    UpdateProposalData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_proposal_or_404,
    get_scenario_or_404,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.proposal.proposal import Proposal

logger = logging.getLogger(__name__)

proposal_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/proposals",
    tags=["Proposals"],
    dependencies=[Depends(get_auth_context)],
)


def _validate_related_scenario_ids(
    handler: Handler,
    related_scenario_ids: list[str] | None,
) -> list[str] | None:
    if related_scenario_ids is None:
        return None
    validated_ids = list(dict.fromkeys(related_scenario_ids))
    for scenario_id in validated_ids:
        get_scenario_or_404(handler, scenario_id)
    return validated_ids


def _proposal_to_api(
    handler: Handler,
    proposal: Proposal,
) -> dict:
    payload = proposal.to_dict()
    payload["related_scenario_ids"] = (
        handler.manager.relationship_manager.get_related_scenario_ids(
            proposal.proposal_id
        )
    )
    return payload


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
    handler: Handler = Depends(get_handler),
) -> list[ProposalData]:
    """List all proposals for a problem."""
    try:
        proposals = handler.manager.list_proposals(
            problem_id=problem_id, scenario_id=scenario_id
        )
        return [_proposal_to_api(handler, proposal) for proposal in proposals]
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
    proposal: PostProposalData,
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ProposalData:
    """Create a proposal for a problem."""
    try:
        proposal_payload = proposal.model_dump(exclude_unset=True)
        proposal_payload["related_scenario_ids"] = _validate_related_scenario_ids(
            handler,
            proposal_payload.get("related_scenario_ids"),
        )
        proposal = handler.manager.create_proposal(problem_id, **proposal_payload)
        logger.info(f"Proposal created: {proposal.proposal_id}")
        return _proposal_to_api(handler, proposal)
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
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ProposalData:
    """Read a proposal by identifier."""
    try:
        proposal = get_proposal_or_404(handler, proposal_id)
        return _proposal_to_api(handler, proposal)
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
    proposal: UpdateProposalData,
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ProposalData:
    """Update a proposal and its related scenario links."""
    try:
        current_proposal = get_proposal_or_404(handler, proposal_id)
        check_version(current_proposal.version, proposal.version)
        proposal_payload = proposal.model_dump(exclude_unset=True, exclude={"version"})
        proposal_payload["related_scenario_ids"] = _validate_related_scenario_ids(
            handler,
            proposal_payload.get("related_scenario_ids"),
        )
        handler.manager.update_proposal(proposal_id, **proposal_payload)
        updated_proposal = handler.manager.read_proposal(proposal_id)
        logger.info(f"Proposal updated: {proposal_id}")
        return _proposal_to_api(handler, updated_proposal)
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
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> None:
    """Delete a proposal from a problem."""
    try:
        get_proposal_or_404(handler, proposal_id)
        handler.manager.delete_proposal(proposal_id)
        logger.info(f"Proposal deleted: {proposal_id}")
    except Exception as e:
        logger.error(f"Error deleting proposal {proposal_id}: {e}")
        raise
