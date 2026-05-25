# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

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
from overtourism.backend.api.v2.utils import (
    api_entity_payload,
    build_evaluation_output,
    check_version,
    get_evaluation_by_id_or_404,
    get_problem_or_404,
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

evaluation_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/evaluations",
    dependencies=[Depends(get_auth_context)],
)


def _evaluation_to_api(evaluation) -> dict:
    return api_entity_payload(evaluation.to_dict())


@evaluation_router.post(
    "/session/{session_id}",
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
        evaluation = handler.manager.create_session_evaluation(
            problem_id,
            session_id,
            data.scenario_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation created for problem {problem_id}")
        return _evaluation_to_api(evaluation)
    except Exception as e:
        logger.error(f"Error creating evaluation for problem {problem_id}: {e}")
        raise


@evaluation_router.get(
    "/session/{session_id}",
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
        evaluations = handler.manager.list_session_evaluations(
            problem_id,
            session_id,
            scenario_id,
        )
        return [_evaluation_to_api(evaluation) for evaluation in evaluations]
    except Exception as e:
        logger.error(f"Error listing evaluations for problem {problem_id}: {e}")
        raise


@evaluation_router.get(
    "/session/{session_id}/{evaluation_id}",
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
        return _evaluation_to_api(evaluation)
    except Exception as e:
        logger.error(
            f"Error reading evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.put(
    "/session/{session_id}/{evaluation_id}",
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
        evaluation = handler.manager.update_session_evaluation(
            problem_id,
            session_id,
            evaluation_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation updated: {evaluation_id} for problem {problem_id}")
        return _evaluation_to_api(evaluation)
    except Exception as e:
        logger.error(
            f"Error updating evaluation {evaluation_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.delete(
    "/session/{session_id}/{evaluation_id}",
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
    "/session/{session_id}/{evaluation_id}/data",
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
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        get_scenario_or_404(handler, problem_id, data.scenario_id)
        evaluation = handler.manager.evaluate_scenario(
            problem_id,
            data.scenario_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation created for problem {problem_id}")
        return _evaluation_to_api(evaluation)
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
    handler: Handler = Depends(get_handler),
) -> list[EvaluationData]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluations = handler.manager.list_evaluations(problem_id, scenario_id)
        return [_evaluation_to_api(evaluation) for evaluation in evaluations]
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
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
        return _evaluation_to_api(evaluation)
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
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
        check_version(current.version, data.version)
        evaluation = handler.manager.update_evaluation(
            problem_id,
            evaluation_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        logger.info(f"Evaluation updated: {evaluation_id} for problem {problem_id}")
        return _evaluation_to_api(evaluation)
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
    data: VersionData | None = None,
    handler: Handler = Depends(get_handler),
) -> dict[str, str]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
        check_version(evaluation.version, None if data is None else data.version)
        handler.manager.delete_evaluation(problem_id, evaluation_id)
        logger.info(f"Evaluation deleted: {evaluation_id} for problem {problem_id}")
        return {"message": "Evaluation deleted successfully"}
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
    handler: Handler = Depends(get_handler),
) -> EvaluationOutputData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        evaluation = get_evaluation_by_id_or_404(handler, problem_id, evaluation_id)
        scenario = get_scenario_or_404(handler, problem_id, evaluation.scenario_id)
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
