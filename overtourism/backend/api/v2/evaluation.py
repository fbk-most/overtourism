# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Query, Response

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
    UpdateEvaluationData,
)
from overtourism.backend.api.v2.utils import (
    build_evaluation_output,
    check_version,
    get_evaluation_by_id_or_404,
    get_problem_or_404,
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    set_version_header,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

evaluation_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/evaluations",
    dependencies=[Depends(get_auth_context)],
)


@evaluation_router.post(
    "",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Problem or scenario does not exist"},
        200: {"description": "Evaluation created"},
    },
)
async def create_evaluation(
    tenant: str,
    problem_id: str,
    data: PostEvaluationData,
    response: Response,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            get_scenario_or_404(handler, problem_id, data.scenario_id)
            evaluation = handler.manager.evaluate_scenario(
                problem_id,
                data.scenario_id,
                ensemble_size=data.ensemble_size,
                **data.kwargs,
            )
        else:
            get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                data.scenario_id,
            )
            evaluation = handler.manager.create_session_evaluation(
                problem_id,
                session_id,
                data.scenario_id,
                ensemble_size=data.ensemble_size,
                **data.kwargs,
            )
        set_version_header(response, evaluation.version)
        logger.info(f"Evaluation created for problem {problem_id}")
        return evaluation.to_dict()
    except Exception as e:
        logger.error(f"Error creating evaluation for problem {problem_id}: {e}")
        raise


@evaluation_router.get(
    "",
    response_model=list[EvaluationData],
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Problem or session does not exist"},
        200: {"description": "Evaluation list"},
    },
)
async def list_evaluations(
    tenant: str,
    problem_id: str,
    scenario_id: str | None = None,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> list[EvaluationData]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            evaluations = handler.manager.list_evaluations(problem_id, scenario_id)
        else:
            get_session_or_404(handler, problem_id, session_id)
            evaluations = handler.manager.list_session_evaluations(
                problem_id,
                session_id,
                scenario_id,
            )
        return [evaluation.to_dict() for evaluation in evaluations]
    except Exception as e:
        logger.error(f"Error listing evaluations for problem {problem_id}: {e}")
        raise


@evaluation_router.get(
    "/{evaluation_id}",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation details"},
    },
)
async def read_evaluation(
    tenant: str,
    problem_id: str,
    evaluation_id: str,
    response: Response,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
        else:
            evaluation = get_session_evaluation_by_id_or_404(
                handler,
                problem_id,
                session_id,
                evaluation_id,
            )
        set_version_header(response, evaluation.version)
        return evaluation.to_dict()
    except Exception as e:
        logger.error(
            f"Error reading evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.put(
    "/{evaluation_id}",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation updated"},
    },
)
async def update_evaluation(
    tenant: str,
    problem_id: str,
    evaluation_id: str,
    data: UpdateEvaluationData,
    response: Response,
    *,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    version: str | None = Header(default=None, alias="Version"),
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            current = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
            check_version(current.version, version)
            evaluation = handler.manager.update_evaluation(
                problem_id,
                evaluation_id,
                ensemble_size=data.ensemble_size,
                **data.kwargs,
            )
        else:
            current = get_session_evaluation_by_id_or_404(
                handler,
                problem_id,
                session_id,
                evaluation_id,
            )
            check_version(current.version, version)
            evaluation = handler.manager.update_session_evaluation(
                problem_id,
                session_id,
                evaluation_id,
                ensemble_size=data.ensemble_size,
                **data.kwargs,
            )
        set_version_header(response, evaluation.version)
        logger.info(f"Evaluation updated: {evaluation_id} for problem {problem_id}")
        return evaluation.to_dict()
    except Exception as e:
        logger.error(
            f"Error updating evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.delete(
    "/{evaluation_id}",
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation deleted"},
    },
)
async def delete_evaluation(
    tenant: str,
    problem_id: str,
    evaluation_id: str,
    *,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    version: str | None = Header(default=None, alias="Version"),
    handler: Handler = Depends(get_handler),
) -> dict[str, str]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
            check_version(evaluation.version, version)
            handler.manager.delete_evaluation(problem_id, evaluation_id)
            message = "Evaluation deleted successfully"
        else:
            evaluation = get_session_evaluation_by_id_or_404(
                handler,
                problem_id,
                session_id,
                evaluation_id,
            )
            check_version(evaluation.version, version)
            handler.manager.delete_session_evaluation(
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


@evaluation_router.get(
    "/{evaluation_id}/data",
    response_model=EvaluationOutputData,
    response_model_exclude_none=True,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Scenario or evaluation does not exist"},
        200: {"description": "Evaluation data"},
    },
)
async def get_data(
    tenant: str,
    problem_id: str,
    evaluation_id: str,
    params: list[str] | None = Query(default=None),
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> EvaluationOutputData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
            scenario = get_scenario_or_404(handler, problem_id, evaluation.scenario_id)
        else:
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
        return build_evaluation_output(
            handler,
            scenario,
            evaluation,
            params=params,
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise
