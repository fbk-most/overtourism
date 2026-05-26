# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v1.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v1.models.scenario import (
    InputEvaluationData,
    OutputData,
    SaveData,
)
from overtourism.backend.api.v1.utils import (
    arrange_data,
    get_problem_editable_indexes,
    get_problem_or_404,
    get_widgets,
    model_values,
    prepare_values,
    scenario_index_diffs,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.scenario.values import values_as_scipy

logger = logging.getLogger(__name__)

scenario_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/scenarios",
    dependencies=[Depends(get_auth_context)],
)


def _matches_requested_session_scenario(
    requested_scenario_id: str,
    session_scenario_id: str,
    session_id: str,
) -> bool:
    if session_scenario_id == requested_scenario_id:
        return True
    return session_scenario_id.startswith(f"{requested_scenario_id}_{session_id}_")


def _read_matching_session_state(
    handler: Handler,
    problem_id: str,
    session_id: str,
    scenario_id: str,
):
    try:
        session = handler.manager.session_manager.read_session(problem_id, session_id)
    except Exception:
        return (None, None)

    candidate_ids: list[str] = []
    if scenario_id in session.drafts:
        candidate_ids.append(scenario_id)

    if session.active_scenario_id is not None and _matches_requested_session_scenario(
        scenario_id,
        session.active_scenario_id,
        session_id,
    ):
        candidate_ids.append(session.active_scenario_id)

    for draft_id in session.drafts:
        if _matches_requested_session_scenario(scenario_id, draft_id, session_id):
            candidate_ids.append(draft_id)

    seen: set[str] = set()
    for candidate_id in candidate_ids:
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        try:
            return (
                handler.manager.session_manager.read_session_scenario(
                    problem_id,
                    session_id,
                    candidate_id,
                ),
                handler.manager.session_manager.read_session_evaluation(
                    problem_id,
                    session_id,
                    candidate_id,
                ),
            )
        except Exception:
            continue

    return (None, None)


@scenario_router.get(
    "/{scenario_id}",
    response_model=OutputData,
    responses={
        500: {"description": "Evaluation error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario data"},
    },
)
async def get_data(
    problem_id: str,
    scenario_id: str,
    session_id: str | None = None,
    language: Literal["it", "en"] = "it",
    handler: Handler = Depends(get_handler),
) -> OutputData:
    """Read the evaluated outputs for a scenario."""
    try:
        manager = handler.manager
        problem = get_problem_or_404(handler, problem_id)

        # If a session exists, return its already-evaluated scenario copy.
        session_scenario = None
        session_evaluation = None
        if session_id is not None:
            session_scenario, session_evaluation = _read_matching_session_state(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )

        if session_scenario is not None and session_evaluation is not None:
            out_data = arrange_data(
                handler,
                session_evaluation.result,
            )
            values = {
                **model_values(handler),
                **values_as_scipy(session_scenario),
            }
            return OutputData(
                problem_id=problem_id,
                scenario_id=scenario_id,
                data=out_data,
                index_diffs=scenario_index_diffs(handler, session_scenario),
                widgets=get_widgets(handler, values, language=language),
                editable_indexes=get_problem_editable_indexes(problem.extras),
            )

        # No active session — return the stored scenario.
        out_data = arrange_data(
            handler,
            manager.read_scenario_data(problem_id, scenario_id),  # .to_dict()
        )
        scenario = manager.read_scenario(problem_id, scenario_id)
        values = {
            **model_values(handler),
            **values_as_scipy(scenario),
        }
        return OutputData(
            problem_id=problem_id,
            scenario_id=scenario_id,
            data=out_data,
            index_diffs=scenario_index_diffs(handler, scenario),
            widgets=get_widgets(handler, values, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error getting data for scenario {scenario_id} in problem {problem_id}: {e}"
        )
        raise


@scenario_router.put(
    "/{scenario_id}",
    response_model=OutputData,
    responses={
        500: {"description": "Evaluation error"},
        404: {"description": "Model does not exist"},
        200: {"description": "Model data"},
    },
)
async def update_data(
    problem_id: str,
    scenario_id: str,
    data: InputEvaluationData,
    session_id: str | None = None,
    language: Literal["it", "en"] = "it",
    handler: Handler = Depends(get_handler),
) -> OutputData:
    """Re-evaluate a scenario with new values."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        values = prepare_values(handler, data.values)
        if session_id is None:
            handler.manager.update_scenario(
                problem_id=problem_id,
                scenario_id=scenario_id,
                values=values,
            )
            scenario = handler.manager.read_scenario(problem_id, scenario_id)
            evaluation = handler.manager.evaluate_scenario(
                problem_id,
                scenario_id,
                ensemble_size=data.ensemble_size,
            )
            out_data = arrange_data(
                handler,
                evaluation.result,
            )
            merged = {
                **model_values(handler),
                **values_as_scipy(scenario),
            }
            index_diffs = scenario_index_diffs(handler, scenario)
        else:
            session_scenario = handler.manager.session_manager.evaluate_session(
                problem_id=problem_id,
                session_id=session_id,
                scenario_id=scenario_id,
                values=values,
                ensemble_size=data.ensemble_size,
            )
            session_evaluation = (
                handler.manager.session_manager.read_session_evaluation(
                    problem_id,
                    session_id,
                    session_scenario.scenario_id,
                )
            )
            out_data = arrange_data(
                handler,
                session_evaluation.result,
            )
            merged = {
                **model_values(handler),
                **values,
            }
            index_diffs = scenario_index_diffs(handler, session_scenario)
        return OutputData(
            data=out_data,
            scenario_id=scenario_id,
            problem_id=problem_id,
            index_diffs=index_diffs,
            widgets=get_widgets(handler, merged, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error updating data for scenario {scenario_id} in problem {problem_id}: {e}"
        )
        raise


@scenario_router.get(
    "/session/{session_id}",
    response_model=OutputData,
    responses={
        500: {"description": "Session error"},
        404: {"description": "Session does not exist"},
        200: {"description": "Session scenario data"},
    },
)
async def resume_session(
    problem_id: str,
    session_id: str,
    language: Literal["it", "en"] = "it",
    handler: Handler = Depends(get_handler),
) -> OutputData:
    """Resume an in-memory session scenario and return its evaluated data."""
    try:
        problem = get_problem_or_404(handler, problem_id)
        session_scenario, session_evaluation = (
            handler.manager.session_manager.resume_session(
                problem_id,
                session_id,
            )
        )
        out_data = arrange_data(
            handler,
            session_evaluation.result,
        )
        values = {
            **model_values(handler),
            **values_as_scipy(session_scenario),
        }
        return OutputData(
            problem_id=problem_id,
            scenario_id=session_scenario.scenario_id,
            data=out_data,
            index_diffs=scenario_index_diffs(handler, session_scenario),
            widgets=get_widgets(handler, values, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error resuming session {session_id} in problem {problem_id}: {e}"
        )
        raise


@scenario_router.post(
    "/{scenario_id}",
    response_model=dict,
    responses={
        500: {"description": "Save error"},
        200: {"description": "Model saved"},
    },
)
async def create_scenario(
    problem_id: str,
    scenario_id: str,
    session_id: str,
    data: SaveData,
    proposal_id: str | None = None,
    handler: Handler = Depends(get_handler),
) -> dict:
    """Persist the current session scenario as a stored scenario."""
    try:
        extras = handler.manager.scenario_extras_from_dict(data.model_dump())
        saved_scenario = handler.manager.session_manager.save_session_scenario(
            problem_id,
            session_id=session_id,
            name=data.scenario_name,
            description=data.scenario_description,
            extras=extras,
            proposal_id=proposal_id,
        )
        logger.info(
            f"Scenario saved: {saved_scenario.scenario_id} for problem {problem_id}"
        )
        return {"message": "Scenario saved!"}
    except Exception as e:
        logger.error(
            f"Error creating scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.delete(
    "/{scenario_id}",
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario deleted"},
    },
)
async def delete_scenario(
    problem_id: str,
    scenario_id: str,
    handler: Handler = Depends(get_handler),
) -> None:
    """Delete a scenario and detach any related proposal link."""
    try:
        handler.manager.delete_scenario(problem_id, scenario_id)
        logger.info(f"Scenario deleted: {scenario_id} for problem {problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise
