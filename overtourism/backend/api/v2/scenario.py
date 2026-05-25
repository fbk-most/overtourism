# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.common import VersionData
from overtourism.backend.api.v2.models.scenario import (
    PostScenarioData,
    SaveScenarioData,
    ScenarioData,
    UpdateScenarioData,
)
from overtourism.backend.api.v2.utils import (
    api_entity_payload,
    check_version,
    get_problem_or_404,
    get_scenario_or_404,
    get_session_scenario_or_404,
    prepare_values,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.scenario.values import values_as_scipy

logger = logging.getLogger(__name__)

scenario_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/scenarios",
    dependencies=[Depends(get_auth_context)],
)


def _scenario_to_api(scenario) -> dict:
    return api_entity_payload(scenario.to_dict())


@scenario_router.get(
    "",
    response_model=list[ScenarioData],
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Scenario list"},
    },
)
async def list_scenarios(
    tenant: str,
    problem_id: str,
    handler: Handler = Depends(get_handler),
) -> list[ScenarioData]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        return [
            _scenario_to_api(scenario)
            for scenario in handler.manager.list_scenarios(problem_id)
        ]
    except Exception as e:
        logger.error(f"Error listing scenarios for problem {problem_id}: {e}")
        raise


@scenario_router.post(
    "/session/{session_id}",
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
        return _scenario_to_api(scenario)
    except Exception as e:
        logger.error(f"Error creating session scenario for problem {problem_id}: {e}")
        raise


@scenario_router.get(
    "/session/{session_id}/{scenario_id}",
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
        return _scenario_to_api(scenario)
    except Exception as e:
        logger.error(
            f"Error reading scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.put(
    "/session/{session_id}/{scenario_id}",
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
        return _scenario_to_api(scenario)
    except Exception as e:
        logger.error(
            f"Error updating scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.post(
    "/session/{session_id}/{scenario_id}",
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
        return _scenario_to_api(saved_scenario)
    except Exception as e:
        logger.error(
            f"Error saving scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.delete(
    "/session/{session_id}/{scenario_id}",
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


@scenario_router.get(
    "/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario details"},
    },
)
async def read_scenario(
    tenant: str,
    problem_id: str,
    scenario_id: str,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        scenario = get_scenario_or_404(handler, problem_id, scenario_id)
        return _scenario_to_api(scenario)
    except Exception as e:
        logger.error(
            f"Error reading scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.put(
    "/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        200: {"description": "Scenario updated"},
    },
)
async def update_scenario(
    tenant: str,
    problem_id: str,
    scenario_id: str,
    data: UpdateScenarioData,
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        current_scenario = get_scenario_or_404(handler, problem_id, scenario_id)
        check_version(current_scenario.version, data.version)
        updated_values = (
            values_as_scipy(current_scenario)
            if data.values is None
            else prepare_values(handler, data.values)
        )
        handler.manager.update_scenario(
            problem_id,
            scenario_id,
            values=updated_values,
            name=data.name,
            description=data.description,
            extras=data.extras,
        )
        scenario = handler.manager.read_scenario(problem_id, scenario_id)
        logger.info(f"Scenario updated: {scenario_id} for problem {problem_id}")
        return _scenario_to_api(scenario)
    except Exception as e:
        logger.error(
            f"Error updating scenario {scenario_id} for problem {problem_id}: {e}"
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
    tenant: str,
    problem_id: str,
    scenario_id: str,
    data: VersionData | None = None,
    handler: Handler = Depends(get_handler),
) -> dict:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        scenario = get_scenario_or_404(handler, problem_id, scenario_id)
        check_version(scenario.version, None if data is None else data.version)
        handler.manager.delete_scenario(problem_id, scenario_id)
        logger.info(f"Scenario deleted: {scenario_id} for problem {problem_id}")
        return {"message": "Scenario deleted successfully"}
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise
