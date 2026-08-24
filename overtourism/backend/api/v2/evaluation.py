# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.executor_utils import call_executor
from overtourism.backend.api.v2.models.common import VersionData
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
    UpdateEvaluationData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_evaluation_or_404,
    get_scenario_or_404,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.evaluation.evaluation import Evaluation

logger = logging.getLogger(__name__)

evaluation_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/evaluations",
    tags=["Evaluations"],
    dependencies=[Depends(get_auth_context)],
)


@evaluation_router.post(
    "",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation created"},
    },
)
async def create_evaluation(
    tenant: str,
    data: PostEvaluationData,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationData:
    try:
        scenario = get_scenario_or_404(handler, data.scenario_id)
        evaluation = handler.manager.create_evaluation(scenario.scenario_id)
        try:
            result = call_executor(scenario.param_overrides)
            evaluation.result = result
        finally:
            handler.manager.save_evaluation(evaluation)
        logger.info(f"Evaluation created for scenario {data.scenario_id}")
        return EvaluationData.from_domain(evaluation)
    except Exception as e:
        logger.error(f"Error creating evaluation for scenario {data.scenario_id}: {e}")
        raise


@evaluation_router.get(
    "",
    response_model=list[EvaluationData],
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Evaluation does not exist"},
        200: {"description": "Evaluation list"},
    },
)
async def list_evaluations(
    tenant: str,
    scenario_id: str | None = None,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> list[EvaluationData]:
    try:
        evaluations = handler.manager.list_evaluations(scenario_id)
        return [EvaluationData.from_domain(evaluation) for evaluation in evaluations]
    except Exception as e:
        logger.error(f"Error listing evaluations: {e}")
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
    evaluation_id: str,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationData:
    try:
        evaluation = get_evaluation_or_404(handler, evaluation_id)
        return EvaluationData.from_domain(evaluation)
    except Exception as e:
        logger.error(f"Error reading evaluation {evaluation_id}: {e}")
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
    evaluation_id: str,
    data: UpdateEvaluationData,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationData:
    try:
        current = get_evaluation_or_404(handler, evaluation_id)
        check_version(current.version, data.version)
        scenario = handler.manager.read_scenario(current.scenario_id)
        evaluation = Evaluation.create_default(
            current.evaluation_id,
            scenario_id=current.scenario_id,
            type=current.type,
            version=current.version,
        )
        try:
            # Call backend executor
            evaluation.result = call_executor(scenario.param_overrides)
        finally:
            handler.manager.save_evaluation(evaluation)
        logger.info(f"Evaluation updated: {evaluation_id}")
        return EvaluationData.from_domain(evaluation)
    except Exception as e:
        logger.error(f"Error updating evaluation {evaluation_id}: {e}")
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
    evaluation_id: str,
    data: VersionData | None = None,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> dict[str, str]:
    try:
        evaluation = get_evaluation_or_404(handler, evaluation_id)
        check_version(evaluation.version, None if data is None else data.version)
        handler.manager.delete_evaluation(evaluation_id)
        logger.info(f"Evaluation deleted: {evaluation_id}")
        return {"message": "Evaluation deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting evaluation {evaluation_id}: {e}")
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
    evaluation_id: str,
    as_snapshot: Annotated[bool, Query()] = True,
    params: Annotated[list[str] | None, Query()] = None,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> EvaluationOutputData:
    try:
        evaluation = get_evaluation_or_404(handler, evaluation_id)
        result = handler.manager.read_evaluation_data(evaluation_id)
        # Re add the query params to the result if they were provided
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
