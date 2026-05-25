# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.session import (
    CreateSessionData,
    SessionData,
    SessionSummaryData,
)
from overtourism.backend.api.v2.utils import (
    get_problem_or_404,
    get_session_or_404,
    session_summary_to_api,
    session_to_api,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

session_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/sessions",
    dependencies=[Depends(get_auth_context)],
)


@session_router.post(
    "",
    response_model=SessionSummaryData,
    responses={
        500: {"description": "Session manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Session created"},
    },
)
async def create_session(
    tenant: str,
    problem_id: str,
    data: CreateSessionData,
    handler: Handler = Depends(get_handler),
) -> SessionSummaryData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        session = handler.manager.session_manager.create_session(
            problem_id,
            uuid4().hex,
            metadata=data.metadata,
        )
        logger.info(f"Session created: {session.session_id} for problem {problem_id}")
        return session_summary_to_api(session)
    except Exception as e:
        logger.error(f"Error creating session for problem {problem_id}: {e}")
        raise


@session_router.get(
    "",
    response_model=list[SessionSummaryData],
    responses={
        500: {"description": "Session manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Session list"},
    },
)
async def list_sessions(
    tenant: str,
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> list[SessionSummaryData]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        return [
            session_summary_to_api(session)
            for session in handler.manager.session_manager.list_sessions(problem_id)
        ]
    except Exception as e:
        logger.error(f"Error listing sessions for problem {problem_id}: {e}")
        raise


@session_router.get(
    "/{session_id}",
    response_model=SessionData,
    responses={
        500: {"description": "Session manager error"},
        404: {"description": "Session does not exist"},
        200: {"description": "Session details"},
    },
)
async def read_session(
    tenant: str,
    problem_id: str,
    session_id: str,
    handler: Handler = Depends(get_handler),
) -> SessionData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        session = get_session_or_404(handler, problem_id, session_id)
        return session_to_api(session)
    except Exception as e:
        logger.error(
            f"Error reading session {session_id} for problem {problem_id}: {e}"
        )
        raise


@session_router.delete(
    "/{session_id}",
    responses={
        500: {"description": "Session manager error"},
        404: {"description": "Session does not exist"},
        200: {"description": "Session deleted"},
    },
)
async def delete_session(
    tenant: str,
    problem_id: str,
    session_id: str,
    handler: Handler = Depends(get_handler),
) -> dict:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        get_session_or_404(handler, problem_id, session_id)
        handler.manager.session_manager.delete_session(problem_id, session_id)
        logger.info(f"Session deleted: {session_id} for problem {problem_id}")
        return {"message": "Session deleted successfully"}
    except Exception as e:
        logger.error(
            f"Error deleting session {session_id} for problem {problem_id}: {e}"
        )
        raise
