# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.scenario import (
    CreateScenarioData,
    ScenarioData,
    UpdateScenarioData,
)
from overtourism.backend.api.v2.utils import (
    check_version,
    get_scenario_or_404,
    raise_immutable_base_scenario_error,
    scenario_to_api,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

scenario_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/scenarios",
    tags=["Scenarios"],
    dependencies=[Depends(get_auth_context)],
)


@scenario_router.get(
    "",
    response_model=ScenarioData | list[ScenarioData],
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Scenario list or base scenario"},
    },
)
async def list_scenarios(
    tenant: str,
    proposal_id: str | None = None,
    base_only: bool = False,
    *,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData | list[ScenarioData]:
    try:
        if base_only:
            names_cfg = BootstrapConfig(tenant)
            scenario = get_scenario_or_404(handler, names_cfg.scenario_id)
            return scenario_to_api(handler, scenario)
        scenarios = handler.manager.list_scenarios(tenant, proposal_id)
        return [scenario_to_api(handler, scenario) for scenario in scenarios]
    except Exception as e:
        logger.error(f"Error listing scenarios: {e}")
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
    scenario_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        scenario = get_scenario_or_404(handler, scenario_id)
        return scenario_to_api(handler, scenario)
    except Exception as e:
        logger.error(f"Error reading scenario {scenario_id}: {e}")
        raise


@scenario_router.post(
    "",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Problem does not exist"},
        200: {"description": "Scenario created"},
    },
)
async def create_scenario(
    tenant: str,
    data: CreateScenarioData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        scenario_payload = data.model_dump(exclude_unset=True)
        scenario_payload["param_overrides"] = scenario_payload.pop("values", {})
        scenario = handler.manager.create_scenario(**scenario_payload)
        logger.info(f"Scenario created: {scenario.scenario_id}")
        return scenario_to_api(handler, scenario)
    except Exception as e:
        logger.error(f"Error creating scenario: {e}")
        raise


@scenario_router.put(
    "/{scenario_id}",
    response_model=ScenarioData,
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        400: {"description": "Base scenario cannot be updated"},
        200: {"description": "Scenario updated"},
    },
)
async def update_scenario(
    tenant: str,
    scenario_id: str,
    data: UpdateScenarioData,
    handler: Annotated[Handler, Depends(get_handler)],
) -> ScenarioData:
    try:
        raise_immutable_base_scenario_error(handler, scenario_id)
        current_scenario = get_scenario_or_404(handler, scenario_id)
        check_version(current_scenario.version, data.version)
        handler.manager.update_scenario(
            scenario_id,
            param_overrides=data.values,
            name=data.name,
            description=data.description,
            extras=data.extras,
        )
        scenario = handler.manager.read_scenario(scenario_id)
        logger.info(f"Scenario updated: {scenario_id}")
        return scenario_to_api(handler, scenario)
    except Exception as e:
        logger.error(f"Error updating scenario {scenario_id}: {e}")
        raise


@scenario_router.delete(
    "/{scenario_id}",
    responses={
        500: {"description": "Scenario manager error"},
        404: {"description": "Scenario does not exist"},
        400: {"description": "Base scenario cannot be deleted"},
        200: {"description": "Scenario deleted"},
    },
)
async def delete_scenario(
    tenant: str,
    scenario_id: str,
    handler: Annotated[Handler, Depends(get_handler)],
) -> dict:
    try:
        raise_immutable_base_scenario_error(handler, scenario_id)
        get_scenario_or_404(handler, scenario_id)
        handler.manager.delete_scenario(scenario_id)
        logger.info(f"Scenario deleted: {scenario_id}")
        return {"message": "Scenario deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting scenario {scenario_id}: {e}")
        raise
