# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.proposal import (
    create_proposal as base_create_proposal,
)
from overtourism.backend.api.v2.proposal import (
    delete_proposal as base_delete_proposal,
)
from overtourism.backend.api.v2.proposal import (
    list_proposals as base_list_proposals,
)
from overtourism.backend.api.v2.proposal import (
    read_proposal as base_read_proposal,
)
from overtourism.backend.api.v2.proposal import (
    update_proposal as base_update_proposal,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.overtourism.backend_extension.api.v2.models.proposal import (
    OvertourismPostProposalData,
    OvertourismProposalData,
    OvertourismUpdateProposalData,
)
from overtourism.overtourism.backend_extension.api.v2.utils.utils import (
    prepare_proposal_payload,
    to_proposal_api_overtourism,
)

logger = logging.getLogger(__name__)

proposal_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/proposals",
    tags=["Proposals"],
    dependencies=[Depends(get_auth_context)],
)


@proposal_router.get(
    "",
    response_model=list[OvertourismProposalData],
    responses={
        500: {"description": "Proposal manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal list"},
    },
)
async def list_proposals(
    tenant: str,
    problem_id: str | None = None,
    scenario_id: str | None = None,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> list[OvertourismProposalData]:
    try:
        listed = await base_list_proposals(
            tenant=tenant,
            problem_id=problem_id,
            scenario_id=scenario_id,
            handler=handler,
        )
        return [to_proposal_api_overtourism(proposal) for proposal in listed]
    except Exception as e:
        logger.error(f"Error listing proposals: {e}")
        raise


@proposal_router.post(
    "",
    response_model=OvertourismProposalData,
    responses={
        500: {"description": "Proposal manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal created"},
    },
)
async def create_proposal(
    tenant: str,
    data: OvertourismPostProposalData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProposalData:
    try:
        payload = prepare_proposal_payload(
            proposal_id=None,
            payload=data.model_dump(exclude_unset=True),
            handler=handler,
        )
        created = await base_create_proposal(
            tenant=tenant,
            data=payload,
            handler=handler,
        )
        return to_proposal_api_overtourism(created)
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        raise


@proposal_router.get(
    "/{proposal_id}",
    response_model=OvertourismProposalData,
    responses={
        500: {"description": "Proposal manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal details"},
    },
)
async def read_proposal(
    tenant: str,
    proposal_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProposalData:
    try:
        read = await base_read_proposal(
            tenant=tenant,
            proposal_id=proposal_id,
            handler=handler,
        )
        return to_proposal_api_overtourism(read)
    except Exception as e:
        logger.error(f"Error reading proposal {proposal_id}: {e}")
        raise


@proposal_router.put(
    "/{proposal_id}",
    response_model=OvertourismProposalData,
    responses={
        500: {"description": "Proposal manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal updated"},
    },
)
async def update_proposal(
    tenant: str,
    proposal_id: str,
    proposal: OvertourismUpdateProposalData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> OvertourismProposalData:
    try:
        payload = prepare_proposal_payload(
            proposal_id=proposal_id,
            payload=proposal.model_dump(exclude_unset=True),
            handler=handler,
        )
        updated = await base_update_proposal(
            tenant=tenant,
            proposal_id=proposal_id,
            data=payload,
            handler=handler,
        )
        return to_proposal_api_overtourism(updated)
    except Exception as e:
        logger.error(f"Error updating proposal {proposal_id}: {e}")
        raise


@proposal_router.delete(
    "/{proposal_id}",
    responses={
        500: {"description": "Proposal manager error"},
        404: {"description": "Proposal does not exist"},
        200: {"description": "Proposal deleted"},
    },
)
async def delete_proposal(
    tenant: str,
    proposal_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> None:
    try:
        await base_delete_proposal(
            tenant=tenant,
            proposal_id=proposal_id,
            handler=handler,
        )
    except Exception as e:
        logger.error(f"Error deleting proposal {proposal_id}: {e}")
        raise
