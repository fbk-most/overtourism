# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.utils.executor_utils import call_schema
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.layer_3.api.schemas import ModelSchema

logger = logging.getLogger(__name__)

configuration_router = APIRouter(
    prefix=TENANT_ROUTE_PREFIX,
    dependencies=[Depends(get_auth_context)],
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
    tenant: str,
) -> ModelSchema:
    """List all available configuration for the given tenant."""
    try:
        return call_schema(tenant)
    except Exception as exc:
        logger.error(f"Error listing configuration: {exc}")
        raise
