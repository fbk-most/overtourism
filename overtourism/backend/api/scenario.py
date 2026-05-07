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
from overtourism.backend.shared.utils import BASE_ROUTE, get_id, get_timestamp
from overtourism.dt_manager.scenario.values import values_as_scipy

logger = logging.getLogger(__name__)

scenario_router = APIRouter(prefix=f"{BASE_ROUTE}/scenarios")


def _evaluation_result_to_dict(result):
    """Normalize a model output or mapping into a plain dictionary."""
    return result.to_dict() if hasattr(result, "to_dict") else result


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
        scenario_manager = manager.get_scenario_manager(problem_id)
        model_evaluator = scenario_manager.model_evaluator

        # If a session exists, return its already-evaluated scenario copy.
        if session_id is not None and scenario_manager.has_session(session_id):
            session_scenario = manager.get_session_scenario(problem_id, session_id)
            session_evaluation = manager.get_session_evaluation(problem_id, session_id)
            out_data = arrange_data(
                mgrs,
                _evaluation_result_to_dict(session_evaluation.result),
            )
            values = {
                **model_evaluator.get_model_values(scenario_manager.model),
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
            mgrs, manager.get_scenario_data(problem_id, scenario_id)
        )
        scenario = scenario_manager.get_scenario(scenario_id)
        values = {
            **model_evaluator.get_model_values(scenario_manager.model),
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
        session_evaluation = manager.get_session_evaluation(problem_id, session_id)
        out_data = arrange_data(
            mgrs,
            _evaluation_result_to_dict(session_evaluation.result),
        )
        scenario_manager = manager.get_scenario_manager(problem_id)
        merged = {
            **scenario_manager.model_evaluator.get_model_values(scenario_manager.model),
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
    """Create and persist a scenario from a session evaluation."""
    try:
        manager = mgrs.manager
        values = prepare_values(mgrs, data.values)
        extras: dict = {}
        if manager.extras_config is not None:
            extras = manager.extras_config.scenario_extras_from_dict(data.model_dump())
        new_id = get_id(scenario_id, session_id)
        now_timestamp = get_timestamp()
        manager.add_scenario(
            problem_id,
            scenario_id=new_id,
            values=values,
            name=data.scenario_name,
            description=data.scenario_description,
            created=now_timestamp,
            updated=now_timestamp,
            extras=extras,
        )
        manager.evaluate_scenario(problem_id, new_id)
        manager.save_scenario(problem_id, new_id, export_outputs=export_outputs)
        manager.close_session(problem_id, session_id)
        if proposal_id is not None:
            manager.link_scenario_to_proposal(
                problem_id,
                proposal_id,
                new_id,
            )
        logger.info(f"Scenario created: {new_id} for problem {problem_id}")
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
        if proposal_id is not None:
            manager.unlink_scenario_from_proposal(
                problem_id,
                proposal_id,
                scenario_id,
            )
        logger.info(f"Scenario deleted: {scenario_id} for problem {problem_id}")
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise
