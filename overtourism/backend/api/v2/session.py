# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from overtourism.backend.api.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
)
from overtourism.backend.api.models.scenario import (
    PostScenarioData,
    SaveScenarioData,
    ScenarioData,
)
from overtourism.backend.api.models.session import (
    CreateSessionData,
    SessionData,
    SessionSummaryData,
)
from overtourism.backend.api.utils.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.utils.dependencies import get_handler
from overtourism.backend.api.utils.executor_utils import call_executor
from overtourism.backend.api.utils.utils import (
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_evaluation_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    scenario_to_api,
)
from overtourism.backend.auth.dependencies import Handler, get_auth_context
from overtourism.backend.auth.models import AuthContext, resolve_session_owner_id

logger = logging.getLogger(__name__)

session_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/sessions",
    tags=["Sessions"],
    dependencies=[Depends(get_auth_context)],
)


def _require_owned_session(
    handler: Handler,
    tenant: str,
    session_id: str,
    context: AuthContext,
):
    session = get_session_or_404(handler, session_id)
    owner_id = resolve_session_owner_id(context, tenant)
    if session.tenant != tenant or session.owner_id != owner_id:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


# ───────────────────────────────────────────────────────────
# Sessions
# ───────────────────────────────────────────────────────────


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
    data: CreateSessionData,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> SessionSummaryData:
    try:
        owner_id = resolve_session_owner_id(context, tenant)
        session = handler.manager.create_session(
            tenant=tenant,
            owner_id=owner_id,
            metadata=data.metadata,
        )
        logger.info(f"Session created: {session.session_id}")
        return SessionSummaryData(
            session_id=session.session_id,
            owner_id=session.owner_id,
            created=session.created,
            updated=session.updated,
            metadata=dict(session.metadata),
            active_scenario_id=session.active_scenario_id,
            draft_ids=list(session.scenarios),
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
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
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> list[SessionSummaryData]:
    try:
        owner_id = resolve_session_owner_id(context, tenant)
        return [
            SessionSummaryData(
                session_id=session.session_id,
                owner_id=session.owner_id,
                created=session.created,
                updated=session.updated,
                metadata=dict(session.metadata),
                active_scenario_id=session.active_scenario_id,
                draft_ids=list(session.scenarios),
            )
            for session in handler.manager.list_sessions()
            if session.tenant == tenant and session.owner_id == owner_id
        ]
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
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
    session_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> SessionData:
    try:
        session = _require_owned_session(handler, tenant, session_id, context)
        return SessionData(
            session_id=session.session_id,
            owner_id=session.owner_id,
            created=session.created,
            updated=session.updated,
            metadata=dict(session.metadata),
            active_scenario_id=session.active_scenario_id,
            draft_ids=list(session.scenarios),
            scenarios=[
                ScenarioData(**scenario_to_api(handler, draft))
                for draft in session.scenarios.values()
            ],
            evaluations={
                scenario_id: EvaluationData.from_domain(evaluation)
                for scenario_id, evaluation in session.evaluations.items()
            },
        )
    except Exception as e:
        logger.error(f"Error reading session {session_id}: {e}")
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
    session_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> dict:
    try:
        _require_owned_session(handler, tenant, session_id, context)
        handler.manager.delete_session(session_id)
        logger.info(f"Session deleted: {session_id}")
        return {"message": "Session deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise


# ───────────────────────────────────────────────────────────
# Session scenarios
# ───────────────────────────────────────────────────────────


@session_router.post(
    "/{session_id}/scenarios",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Problem or base scenario does not exist"},
        200: {"description": "Draft scenario created"},
    },
)
async def create_session_scenario(
    tenant: str,
    session_id: str,
    data: PostScenarioData,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        _require_owned_session(handler, tenant, session_id, context)
        get_scenario_or_404(tenant, handler, data.base_scenario_id)
        scenario = handler.manager.create_session_scenario(
            session_id,
            data.base_scenario_id,
            param_overrides=data.values,
        )
        logger.info(f"Session draft created: {scenario.scenario_id}")
        return scenario_to_api(handler, scenario)
    except Exception as e:
        logger.error(f"Error creating session scenario: {e}")
        raise


@session_router.get(
    "/{session_id}/scenarios/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario details"},
    },
)
async def read_session_scenario(
    tenant: str,
    session_id: str,
    scenario_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        session = _require_owned_session(handler, tenant, session_id, context)
        scenario = get_session_scenario_or_404(handler, session_id, scenario_id)
        return scenario_to_api(handler, scenario)
    except Exception as e:
        logger.error(f"Error reading scenario {scenario_id}: {e}")
        raise


@session_router.post(
    "/{session_id}/scenarios/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Session scenario does not exist"},
        200: {"description": "Scenario persisted"},
    },
)
async def save_scenario(
    tenant: str,
    session_id: str,
    scenario_id: str,
    data: SaveScenarioData,
    *,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        _require_owned_session(handler, tenant, session_id, context)
        get_session_scenario_or_404(handler, session_id, scenario_id)
        saved_scenario = handler.manager.save_session_scenario(
            session_id,
            scenario_id,
            **data.model_dump(exclude={"version"}),
        )
        logger.info(f"Scenario saved: {scenario_id}")
        return scenario_to_api(handler, saved_scenario)
    except Exception as e:
        logger.error(f"Error saving scenario {scenario_id}: {e}")
        raise


# ───────────────────────────────────────────────────────────
# Session evaluations
# ───────────────────────────────────────────────────────────


@session_router.post(
    "/{session_id}/evaluations",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Problem or scenario does not exist"},
        200: {"description": "Evaluation created"},
    },
)
async def create_session_evaluation(
    tenant: str,
    session_id: str,
    data: PostEvaluationData,
    *,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationData:
    try:
        _require_owned_session(handler, tenant, session_id, context)
        get_session_scenario_or_404(handler, session_id, data.scenario_id)
        scenario = handler.manager.read_session_scenario(session_id, data.scenario_id)
        evaluation = handler.manager.build_running_evaluation(
            uuid4().hex,
            scenario_id=scenario.scenario_id,
        )
        execution_registry = getattr(handler, "execution_manager_registry", None)
        if execution_registry is not None:
            evaluation = execution_registry.get(tenant).execute_evaluation(
                evaluation,
                scenario,
                ensemble_size=data.ensemble_size,
            )
        else:
            result = call_executor(tenant, scenario.param_overrides)
            evaluation.result = result
        handler.manager.create_session_evaluation(
            session_id,
            scenario.scenario_id,
            evaluation,
        )
        logger.info("Evaluation created")
        return EvaluationData.from_domain(evaluation)
    except Exception as e:
        logger.error(f"Error creating evaluation: {e}")
        raise


@session_router.get(
    "/{session_id}/evaluations/{evaluation_id}",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation details"},
    },
)
async def read_session_evaluation(
    tenant: str,
    session_id: str,
    scenario_id: str | None = None,
    evaluation_id: str | None = None,
    *,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationData:
    try:
        _require_owned_session(handler, tenant, session_id, context)

        if scenario_id is not None:
            evaluation = get_session_evaluation_or_404(
                handler,
                session_id,
                scenario_id,
            )
        elif evaluation_id is not None:
            evaluation = get_session_evaluation_by_id_or_404(
                handler,
                session_id,
                evaluation_id,
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="Either scenario_id or evaluation_id must be provided",
            )
        return EvaluationData.from_domain(evaluation)
    except Exception as e:
        logger.error(f"Error reading evaluation {scenario_id or evaluation_id}: {e}")
        raise


@session_router.get(
    "/{session_id}/evaluations/{evaluation_id}/data",
    response_model=EvaluationOutputData,
    response_model_exclude_none=True,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Scenario or evaluation does not exist"},
        200: {"description": "Evaluation data"},
    },
)
async def get_session_data(
    tenant: str,
    session_id: str,
    evaluation_id: str,
    as_snapshot: Annotated[bool, Query()] = True,
    params: Annotated[list[str] | None, Query()] = None,
    *,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationOutputData:
    try:
        _require_owned_session(handler, tenant, session_id, context)
        evaluation = get_session_evaluation_by_id_or_404(
            handler, session_id, evaluation_id
        )
        return EvaluationOutputData(
            scenario_id=evaluation.scenario_id,
            evaluation_id=evaluation.evaluation_id,
            data=evaluation.result,
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for evaluation {evaluation_id}: {e}"
        )
        raise
