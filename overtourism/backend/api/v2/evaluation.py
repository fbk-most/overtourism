# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, Response

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
    PostEvaluationData,
)
from overtourism.backend.api.v2.utils import (
    arrange_data,
    get_problem_editable_indexes,
    get_problem_or_404,
    get_session_evaluation_or_404,
    get_session_scenario_or_404,
    get_widgets,
    model_values,
    scenario_index_diffs,
    set_version_header,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.scenario.values import values_as_scipy

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
    scenario_id: str,
    response: Response,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            evaluation = handler.manager.read_latest_evaluation(problem_id, scenario_id)
        else:
            evaluation = get_session_evaluation_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
        set_version_header(response, evaluation.version)
        return evaluation.to_dict()
    except Exception as e:
        logger.error(
            f"Error reading evaluation for scenario {scenario_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.get(
    "/data",
    response_model=EvaluationOutputData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Scenario or evaluation does not exist"},
        200: {"description": "Evaluation data"},
    },
)
async def get_data(
    tenant: str,
    problem_id: str,
    scenario_id: str,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    language: Literal["it", "en"] = "it",
    handler: Handler = Depends(get_handler),
) -> EvaluationOutputData:
    try:
        problem = get_problem_or_404(handler, tenant, problem_id)

        if session_id is None:
            scenario = handler.manager.read_scenario(problem_id, scenario_id)
            output_data = handler.manager.read_scenario_data(problem_id, scenario_id)
        else:
            scenario = get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
            output_data = handler.manager.read_session_scenario_data(
                problem_id,
                session_id,
                scenario_id,
            )

        values = {
            **model_values(handler),
            **values_as_scipy(scenario),
        }
        return EvaluationOutputData(
            problem_id=problem_id,
            scenario_id=scenario.scenario_id,
            data=arrange_data(handler, output_data),
            index_diffs=scenario_index_diffs(handler, scenario),
            widgets=get_widgets(handler, values, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for scenario {scenario_id} in problem {problem_id}: {e}"
        )
        raise
