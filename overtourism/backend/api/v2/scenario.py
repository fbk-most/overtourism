# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Response

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.scenario import (
    PostScenarioData,
    SaveScenarioData,
    ScenarioData,
    UpdateScenarioData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_problem_or_404,
    get_session_scenario_or_404,
    prepare_values,
    set_version_header,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.dt_manager.scenario.values import values_as_scipy

logger = logging.getLogger(__name__)

scenario_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/scenarios",
    dependencies=[Depends(get_auth_context)],
)


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
            scenario.to_dict()
            for scenario in handler.manager.list_scenarios(problem_id)
        ]
    except Exception as e:
        logger.error(f"Error listing scenarios for problem {problem_id}: {e}")
        raise


@scenario_router.post(
    "",
    response_model=dict,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Problem or base scenario does not exist"},
        200: {"description": "Draft scenario created"},
    },
)
async def create_scenario(
    tenant: str,
    problem_id: str,
    data: PostScenarioData,
    response: Response,
    session_id: str = Header(alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> dict[str, str]:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        scenario = handler.manager.create_session_scenario(
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
        set_version_header(response, scenario.version)
        logger.info(
            f"Session draft created: {scenario.scenario_id} for problem {problem_id}"
        )
        return {"scenario_id": scenario.scenario_id}
    except Exception as e:
        logger.error(f"Error creating session scenario for problem {problem_id}: {e}")
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
    response: Response,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            scenario = handler.manager.read_scenario(problem_id, scenario_id)
        else:
            scenario = get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
        set_version_header(response, scenario.version)
        return scenario.to_dict()
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
    response: Response,
    *,
    session_id: str | None = Header(default=None, alias="Session-ID"),
    version: str | None = Header(default=None, alias="Version"),
    handler: Handler = Depends(get_handler),
) -> ScenarioData:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            current_scenario = handler.manager.read_scenario(problem_id, scenario_id)
        else:
            current_scenario = get_session_scenario_or_404(
                handler,
                problem_id,
                session_id,
                scenario_id,
            )
        check_version(current_scenario.version, version)
        updated_values = (
            values_as_scipy(current_scenario)
            if data.values is None
            else prepare_values(handler, data.values)
        )
        if session_id is None:
            handler.manager.update_scenario(
                problem_id,
                scenario_id,
                values=updated_values,
                name=data.name,
                description=data.description,
                extras=data.extras,
            )
            scenario = handler.manager.read_scenario(problem_id, scenario_id)
        else:
            scenario = handler.manager.update_session_scenario(
                problem_id,
                session_id,
                scenario_id,
                values=updated_values,
                name=data.name,
                description=data.description,
                extras=data.extras,
            )
        set_version_header(response, scenario.version)
        logger.info(f"Scenario updated: {scenario_id} for problem {problem_id}")
        return scenario.to_dict()
    except Exception as e:
        logger.error(
            f"Error updating scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise


@scenario_router.post(
    "/{scenario_id}",
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
    scenario_id: str,
    data: SaveScenarioData,
    response: Response,
    *,
    session_id: str = Header(alias="Session-ID"),
    version: str | None = Header(default=None, alias="Version"),
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
        check_version(current_scenario.version, version)
        saved_scenario = handler.manager.save_session_scenario(
            problem_id,
            session_id,
            scenario_id=scenario_id,
            name=data.name,
            description=data.description,
            extras=data.extras,
            proposal_id=data.proposal_id,
        )
        set_version_header(response, saved_scenario.version)
        logger.info(f"Scenario saved: {scenario_id} for problem {problem_id}")
        return saved_scenario.to_dict()
    except Exception as e:
        logger.error(
            f"Error saving scenario {scenario_id} for problem {problem_id}: {e}"
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
    version: str | None = Header(default=None, alias="Version"),
    session_id: str | None = Header(default=None, alias="Session-ID"),
    handler: Handler = Depends(get_handler),
) -> dict:
    try:
        get_problem_or_404(handler, tenant, problem_id)
        if session_id is None:
            scenario = handler.manager.read_scenario(problem_id, scenario_id)
            check_version(scenario.version, version)
            handler.manager.delete_scenario(problem_id, scenario_id)
            logger.info(f"Scenario deleted: {scenario_id} for problem {problem_id}")
            return {"message": "Scenario deleted successfully"}

        scenario = get_session_scenario_or_404(
            handler,
            problem_id,
            session_id,
            scenario_id,
        )
        check_version(scenario.version, version)
        handler.manager.delete_session_scenario(problem_id, session_id, scenario_id)
        logger.info(f"Session scenario deleted: {scenario_id} for problem {problem_id}")
        return {"message": "Session scenario deleted successfully"}
    except Exception as e:
        logger.error(
            f"Error deleting scenario {scenario_id} for problem {problem_id}: {e}"
        )
        raise
