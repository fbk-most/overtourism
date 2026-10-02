# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.executor_utils import call_schema
from overtourism.backend.auth.identity.authorization import require_territory_access
from overtourism.backend.utils.config import TERRITORY_ROUTE_PREFIX
from overtourism.layer_3.api.schemas import ModelSchema

logger = logging.getLogger(__name__)

configuration_router = APIRouter(
    prefix=TERRITORY_ROUTE_PREFIX,
    dependencies=[Depends(require_territory_access)],
)


@configuration_router.get(
    "/configuration",
    response_model=ModelSchema,
    responses={
        500: {"description": "View manager error"},
        200: {"description": "Configuration api"},
    },
)
async def get_configuration(
    territory: str,
) -> ModelSchema:
    """List all available configuration for the given territory."""
    try:
        return call_schema(territory)
    except Exception as exc:
        logger.error(f"Error listing configuration: {exc}")
        raise
