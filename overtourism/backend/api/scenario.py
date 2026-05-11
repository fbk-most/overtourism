# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends

from overtourism.backend.api.dependencies import get_managers
from overtourism.backend.api.utils import (
    arrange_data,
    get_problem_or_404,
    get_widgets,
    prepare_values,
)
from overtourism.backend.managers import Managers
from overtourism.backend.shared.models.scenario import (
    InputEvaluationData,
    OutputData,
    SaveData,
)
from overtourism.backend.shared.problem_metadata import get_problem_editable_indexes
from overtourism.backend.shared.utils import BASE_ROUTE
from overtourism.dt_manager.scenario.values import values_as_scipy

logger = logging.getLogger(__name__)

scenario_router = APIRouter(prefix=f"{BASE_ROUTE}/scenarios")


def _evaluation_result_to_dict(result):
    """Normalize a model output or mapping into a plain dictionary."""
    return result.to_dict() if hasattr(result, "to_dict") else result


def _model_values(manager) -> dict:
    """Return the base model values exposed by the facade manager."""
    return manager.model_evaluator.get_model_values(manager.model)


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
    mgrs: Managers = Depends(get_managers),
) -> OutputData:
    """Read the evaluated outputs for a scenario."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)

        # If a session exists, return its already-evaluated scenario copy.
        session_scenario = None
        session_evaluation = None
        if session_id is not None:
            try:
                session_scenario = manager.read_session_scenario(problem_id, session_id)
                session_evaluation = manager.read_session_evaluation(
                    problem_id, session_id
                )
            except Exception:
                session_scenario = None
                session_evaluation = None

        if session_scenario is not None and session_evaluation is not None:
            out_data = arrange_data(
                mgrs,
                _evaluation_result_to_dict(session_evaluation.result),
            )
            values = {
                **_model_values(manager),
                **values_as_scipy(session_scenario),
            }
            return OutputData(
                problem_id=problem_id,
                scenario_id=scenario_id,
                data=out_data,
                index_diffs=session_scenario.index_diffs,
                widgets=get_widgets(mgrs, values, language=language),
                editable_indexes=get_problem_editable_indexes(problem.extras),
            )

        # No active session — return the stored scenario.
        out_data = arrange_data(
            mgrs, manager.read_scenario_data(problem_id, scenario_id)
        )
        scenario = manager.read_scenario(problem_id, scenario_id)
        values = {
            **_model_values(manager),
            **values_as_scipy(scenario),
        }
        return OutputData(
            problem_id=problem_id,
            scenario_id=scenario_id,
            data=out_data,
            index_diffs=scenario.index_diffs,
            widgets=get_widgets(mgrs, values, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error getting data for scenario {scenario_id} in problem {problem_id}: {e}"
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
    mgrs: Managers = Depends(get_managers),
) -> OutputData:
    """Resume an in-memory session scenario and return its evaluated data."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)
        session_scenario, session_evaluation = manager.resume_session(
            problem_id,
            session_id,
        )
        out_data = arrange_data(
            mgrs,
            _evaluation_result_to_dict(session_evaluation.result),
        )
        values = {
            **_model_values(manager),
            **values_as_scipy(session_scenario),
        }
        return OutputData(
            problem_id=problem_id,
            scenario_id=session_scenario.scenario_id,
            data=out_data,
            index_diffs=session_scenario.index_diffs,
            widgets=get_widgets(mgrs, values, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error resuming session {session_id} in problem {problem_id}: {e}"
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
    session_id: str,
    language: Literal["it", "en"] = "it",
    mgrs: Managers = Depends(get_managers),
) -> OutputData:
    """Re-evaluate a scenario with new values."""
    try:
        manager = mgrs.manager
        problem = get_problem_or_404(mgrs, problem_id)
        values = prepare_values(mgrs, data.values)
        session_scenario = manager.evaluate_session(
            problem_id=problem_id,
            session_id=session_id,
            scenario_id=scenario_id,
            values=values,
            ensemble_size=data.ensemble_size,
        )
        session_evaluation = manager.read_session_evaluation(problem_id, session_id)
        out_data = arrange_data(
            mgrs,
            _evaluation_result_to_dict(session_evaluation.result),
        )
        merged = {
            **_model_values(manager),
            **values,
        }
        return OutputData(
            data=out_data,
            scenario_id=scenario_id,
            problem_id=problem_id,
            index_diffs=session_scenario.index_diffs,
            widgets=get_widgets(mgrs, merged, language=language),
            editable_indexes=get_problem_editable_indexes(problem.extras),
        )
    except Exception as e:
        logger.error(
            f"Error updating data for scenario {scenario_id} in problem {problem_id}: {e}"
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
    export_outputs: bool = False,
    mgrs: Managers = Depends(get_managers),
) -> dict:
    """Persist the current session scenario as a stored scenario."""
    try:
        manager = mgrs.manager
        extras: dict = {}
        if manager.extras_config is not None:
            extras = manager.extras_config.scenario_extras_from_dict(data.model_dump())
        saved_scenario = manager.save_session_scenario(
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
    proposal_id: str | None = None,
    mgrs: Managers = Depends(get_managers),
) -> None:
    """Delete a scenario and detach any related proposal link."""
    try:
        manager = mgrs.manager
        manager.delete_scenario(problem_id, scenario_id)
        logger.info(f"Scenario deleted: {scenario_id} for problem {problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise
