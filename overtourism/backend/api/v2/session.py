# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
)
from overtourism.backend.api.v2.models.scenario import (
    PostScenarioData,
    SaveScenarioData,
    ScenarioData,
)
from overtourism.backend.api.v2.models.session import (
    CreateSessionData,
    SessionData,
    SessionSummaryData,
)
from overtourism.backend.api.v2.session_ownership import (
    can_claim_session_ownership,
    claim_session_ownership,
    delete_session_ownership,
    list_owned_session_ids,
    require_session_ownership,
)
from overtourism.backend.api.v2.utils import (
    arrange_data,
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_evaluation_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    prepare_values,
    scenario_to_api,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

session_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/sessions",
    tags=["Sessions"],
    dependencies=[Depends(get_auth_context)],
)

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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> SessionSummaryData:
    try:
        session = handler.manager.create_session(metadata=data.metadata)
        try:
            claim_session_ownership(handler, tenant, session.session_id, context)
        except Exception:
            handler.manager.delete_session(session.session_id)
            raise
        logger.info(f"Session created: {session.session_id}")
        return SessionSummaryData(
            session_id=session.session_id,
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> list[SessionSummaryData]:
    try:
        session_ids = set(list_owned_session_ids(handler, tenant, context))
        return [
            SessionSummaryData(
                session_id=session.session_id,
                created=session.created,
                updated=session.updated,
                metadata=dict(session.metadata),
                active_scenario_id=session.active_scenario_id,
                draft_ids=list(session.scenarios),
            )
            for session in handler.manager.list_sessions()
            if session.session_id in session_ids
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> SessionData:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        session = get_session_or_404(handler, session_id)
        return SessionData(
            session_id=session.session_id,
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> dict:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        get_session_or_404(handler, session_id)
        handler.manager.delete_session(session_id)
        delete_session_ownership(handler, tenant, session_id)
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ScenarioData:
    try:
        get_session_or_404(handler, session_id)
        get_scenario_or_404(handler, data.base_scenario_id)
        can_claim_session_ownership(
            handler,
            tenant,
            session_id,
            context,
        )
        values = prepare_values(handler, data.values)
        scenario = handler.manager.create_session_scenario(
            session_id,
            data.base_scenario_id,
            values=values,
        )
        try:
            claim_session_ownership(handler, tenant, session_id, context)
        except Exception:
            handler.manager.delete_session(session_id)
            raise
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ScenarioData:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        scenario = get_session_scenario_or_404(
            handler,
            session_id,
            scenario_id,
        )
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> ScenarioData:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        get_session_scenario_or_404(
            handler,
            session_id,
            scenario_id,
        )
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> EvaluationData:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        get_session_scenario_or_404(
            handler,
            session_id,
            data.scenario_id,
        )
        evaluation = handler.manager.create_session_evaluation(
            session_id,
            data.scenario_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
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
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> EvaluationData:
    try:
        require_session_ownership(handler, tenant, session_id, context)

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
        logger.error(
            f"Error reading evaluation {scenario_id or evaluation_id} in problem {problem_id}: {e}"
        )
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
    as_snapshot: bool = Query(default=True),
    params: list[str] | None = Query(default=None),
    context: AuthContext = Depends(get_auth_context),
    handler: Handler = Depends(get_handler),
    problem_id: str | None = None,
) -> EvaluationOutputData:
    try:
        require_session_ownership(handler, tenant, session_id, context)
        evaluation = get_session_evaluation_by_id_or_404(
            handler,
            session_id,
            evaluation_id,
        )
        result = arrange_data(
            handler,
            evaluation.result,
            params=params,
            as_snapshot=as_snapshot,
        )
        return EvaluationOutputData(
            scenario_id=evaluation.scenario_id,
            evaluation_id=evaluation.evaluation_id,
            data=result,
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for evaluation {evaluation_id}: {e}"
        )
        raise
