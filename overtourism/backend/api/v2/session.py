# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Query

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.common import VersionData
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
    UpdateEvaluationData,
)
from overtourism.backend.api.v2.models.scenario import (
    PostScenarioData,
    SaveScenarioData,
    ScenarioData,
    UpdateScenarioData,
)
from overtourism.backend.api.v2.models.session import (
    CreateSessionData,
    SessionData,
    SessionSummaryData,
)
from overtourism.backend.api.v2.utils import (
    arrange_data,
    check_version,
    get_problem_or_404,
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    prepare_values,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.scenario.values import values_as_scipy

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
        return SessionSummaryData(
            problem_id=session.problem_id,
            session_id=session.session_id,
            created=session.created,
            updated=session.updated,
            metadata=dict(session.metadata),
            active_scenario_id=session.active_scenario_id,
            draft_ids=list(session.drafts),
        )
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
            SessionSummaryData(
                problem_id=session.problem_id,
                session_id=session.session_id,
                created=session.created,
                updated=session.updated,
                metadata=dict(session.metadata),
                active_scenario_id=session.active_scenario_id,
                draft_ids=list(session.drafts),
            )
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
        return SessionData(
            problem_id=session.problem_id,
            session_id=session.session_id,
            created=session.created,
            updated=session.updated,
            metadata=dict(session.metadata),
            active_scenario_id=session.active_scenario_id,
            draft_ids=list(session.drafts),
            drafts=[
                ScenarioData(**draft.to_dict()) for draft in session.drafts.values()
            ],
            evaluations={
                scenario_id: EvaluationData(**evaluation.to_dict())
                for scenario_id, evaluation in session.evaluations.items()
            },
        )
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
    problem_id: str,
    session_id: str,
    data: PostScenarioData,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        get_scenario_or_404(handler, problem_id, data.base_scenario_id)
        scenario = handler.manager.session_manager.create_session_scenario(
            problem_id,
            session_id,
            data.base_scenario_id,
            values=(
                None if data.values is None else prepare_values(handler, data.values)
            ),
            name=data.name,
            description=data.description,
            extras=data.extras,
        )
        logger.info(
            f"Session draft created: {scenario.scenario_id} for problem {problem_id}"
        )
        return scenario.to_dict()
    except Exception as e:
        logger.error(f"Error creating session scenario for problem {problem_id}: {e}")
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
    problem_id: str,
    session_id: str,
    scenario_id: str,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        return scenario.to_dict()
    except Exception as e:
        logger.error(
            f"Error reading scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@session_router.put(
    "/{session_id}/scenarios/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario updated"},
    },
)
async def update_session_scenario(
    tenant: str,
    problem_id: str,
    session_id: str,
    scenario_id: str,
    data: UpdateScenarioData,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current_scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        check_version(current_scenario.version, data.version)
        updated_values = (
            values_as_scipy(current_scenario)
            if data.values is None
            else prepare_values(handler, data.values)
        )
        scenario = handler.manager.session_manager.update_session_scenario(
            problem_id,
            session_id,
            scenario_id,
            values=updated_values,
            name=data.name,
            description=data.description,
            extras=data.extras,
        )
        logger.info(f"Scenario updated: {scenario_id} for problem {problem_id}")
        return scenario.to_dict()
    except Exception as e:
        logger.error(
            f"Error updating scenario {scenario_id} for problem {problem_id}: {e}"
        )
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
    problem_id: str,
    session_id: str,
    scenario_id: str,
    data: SaveScenarioData,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current_scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        check_version(current_scenario.version, data.version)
        saved_scenario = handler.manager.session_manager.save_session_scenario(
            problem_id,
            session_id,
            scenario_id=scenario_id,
            name=data.name,
            description=data.description,
            extras=data.extras,
            proposal_id=data.proposal_id,
        )
        logger.info(f"Scenario saved: {scenario_id} for problem {problem_id}")
        return saved_scenario.to_dict()
    except Exception as e:
        logger.error(
            f"Error saving scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@session_router.delete(
    "/{session_id}/scenarios/{scenario_id}",
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario deleted"},
    },
)
async def delete_session_scenario(
    tenant: str,
    problem_id: str,
    session_id: str,
    scenario_id: str,
    data: VersionData | None = None,
    handler: Handler = Depends(get_handler),
) -> dict:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        check_version(scenario.version, None if data is None else data.version)
        handler.manager.session_manager.delete_session_scenario(
            problem_id,
            session_id,
            scenario_id,
        )
        logger.info(f"Session scenario deleted: {scenario_id} for problem {problem_id}")
        return {"message": "Session scenario deleted successfully"}
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


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
    problem_id: str,
    session_id: str,
    data: PostEvaluationData,
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            data.scenario_id,
        )
        evaluation = handler.manager.session_manager.create_session_evaluation(
            problem_id,
            session_id,
            data.scenario_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation created for problem {problem_id}")
        return evaluation.to_dict()
    except Exception as e:
        logger.error(f"Error creating evaluation for problem {problem_id}: {e}")
        raise


@session_router.get(
    "/{session_id}/evaluations",
    response_model=list[EvaluationData],
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Problem or session does not exist"},
        200: {"description": "Evaluation list"},
    },
)
async def list_session_evaluations(
    tenant: str,
    problem_id: str,
    session_id: str,
    scenario_id: str | None = None,
    handler: Handler = Depends(get_handler),
) -> list[EvaluationData]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        get_session_or_404(handler, problem_id, session_id)
        evaluations = handler.manager.session_manager.list_session_evaluations(
            problem_id,
            session_id,
            scenario_id,
        )
        return [evaluation.to_dict() for evaluation in evaluations]
    except Exception as e:
        logger.error(f"Error listing evaluations for problem {problem_id}: {e}")
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
    problem_id: str,
    session_id: str,
    evaluation_id: str,
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_session_evaluation_by_id_or_404(
            handler,
            problem_id,
            session_id,
            evaluation_id,
        )
        return evaluation.to_dict()
    except Exception as e:
        logger.error(
            f"Error reading evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@session_router.put(
    "/{session_id}/evaluations/{evaluation_id}",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation updated"},
    },
)
async def update_session_evaluation(
    tenant: str,
    problem_id: str,
    session_id: str,
    evaluation_id: str,
    data: UpdateEvaluationData,
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current = get_session_evaluation_by_id_or_404(
            handler,
            problem_id,
            session_id,
            evaluation_id,
        )
        check_version(current.version, data.version)
        evaluation = handler.manager.session_manager.update_session_evaluation(
            problem_id,
            session_id,
            evaluation_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation updated: {evaluation_id} for problem {problem_id}")
        return evaluation.to_dict()
    except Exception as e:
        logger.error(
            f"Error updating evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@session_router.delete(
    "/{session_id}/evaluations/{evaluation_id}",
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation deleted"},
    },
)
async def delete_session_evaluation(
    tenant: str,
    problem_id: str,
    session_id: str,
    evaluation_id: str,
    data: VersionData | None = None,
    handler: Handler = Depends(get_handler),
) -> dict[str, str]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_session_evaluation_by_id_or_404(
            handler,
            problem_id,
            session_id,
            evaluation_id,
        )
        check_version(evaluation.version, None if data is None else data.version)
        handler.manager.session_manager.delete_session_evaluation(
            problem_id,
            session_id,
            evaluation_id,
        )
        message = "Session evaluation deleted successfully"
        logger.info(f"Evaluation deleted: {evaluation_id} for problem {problem_id}")
        return {"message": message}
    except Exception as e:
        logger.error(
            f"Error deleting evaluation {evaluation_id} in problem {problem_id}: {e}"
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
    problem_id: str,
    session_id: str,
    evaluation_id: str,
    params: list[str] | None = Query(default=None),
    handler: Handler = Depends(get_handler),
) -> EvaluationOutputData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_session_evaluation_by_id_or_404(
            handler,
            problem_id,
            session_id,
            evaluation_id,
        )
        scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            evaluation.scenario_id,
        )
        result = arrange_data(handler, evaluation.result, params=params)
        return EvaluationOutputData(
            problem_id=scenario.problem_id,
            scenario_id=scenario.scenario_id,
            evaluation_id=evaluation.evaluation_id,
            data=(
                {}
                if result is None
                else result.to_snapshot()
                if hasattr(result, "to_snapshot")
                else result
            ),
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise
