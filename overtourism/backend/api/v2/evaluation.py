# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

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
    evaluation_result_to_dict,
    get_problem_or_404,
    get_session_evaluation_or_404,
    get_session_scenario_or_404,
    set_version_header,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

evaluation_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/problems/{{problem_id}}/evaluations",
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
        if session_id is not None:
            session_scenario = get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                data.scenario_id,
            )
            evaluation = handler.manager.create_session_evaluation(
                problem_id,
                session_id,
                session_scenario.scenario_id,
                ensemble_size=data.ensemble_size,
                **data.kwargs,
            )
        else:
            evaluation = handler.manager.evaluate_scenario(
                problem_id,
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
            evaluation = handler.manager.read_latest_evaluation(scenario_id)
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
    handler: Handler = Depends(get_handler),
    data: bool = True,
    kpis: bool = True,
) -> EvaluationOutputData:
    try:
        get_problem_or_404(handler, tenant, problem_id)

        if session_id is None:
            output_data = handler.manager.read_scenario_data(
                problem_id, scenario_id
            ).to_dict()
        else:
            scenario = get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
            evaluation = get_session_evaluation_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
            output_data = evaluation_result_to_dict(evaluation.result)
        return EvaluationOutputData(
            problem_id=problem_id,
            scenario_id=scenario.scenario_id,
            data=arrange_data(handler, output_data),
        )
    except Exception as e:
        logger.error(
            f"Error getting evaluation data for scenario {scenario_id} in problem {problem_id}: {e}"
        )
        raise


@evaluation_router.put(
    "/data",
    response_model=EvaluationData,
    responses={
        500: {"description": "Evaluation manager error"},
        404: {"description": "Problem or scenario does not exist"},
        200: {"description": "Evaluation updated"},
    },
)
async def update_evaluation(
    tenant: str,
    problem_id: str,
    scenario_id: str,
    data: PostEvaluationData,
    response: Response,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> EvaluationData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        session_scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            data.scenario_id,
        )
        evaluation = get_session_evaluation_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        if evaluation.scenario_id != session_scenario.scenario_id:
            raise ValueError(
                f"Scenario ID mismatch between evaluation ({evaluation.scenario_id}) and provided base scenario ({session_scenario.scenario_id})"
            )
        evaluation = handler.manager.create_session_evaluation(
            problem_id,
            session_id,
            session_scenario.scenario_id,
            ensemble_size=data.ensemble_size,
            **data.kwargs,
        )
        set_version_header(response, evaluation.version)
        logger.info(f"Evaluation updated for problem {problem_id}")
        return evaluation.to_dict()
    except Exception as e:
        logger.error(f"Error updating evaluation for problem {problem_id}: {e}")
        raise
