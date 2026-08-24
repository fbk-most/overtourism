# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.config import TENANT_ROUTE_PREFIX
from overtourism.overtourism.backend_extension.api.models.widgets import Widgets
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.api.utils.executor_utils import call_schema

logger = logging.getLogger(__name__)

widget_router = APIRouter(
    prefix=TENANT_ROUTE_PREFIX,
    dependencies=[Depends(get_auth_context)],
)


@widget_router.get(
    "/widgets",
    response_model=list[Widgets],
    responses={
        500: {"description": "View manager error"},
        200: {"description": "Widget list"},
    },
)
async def list_widgets(
    tenant: str,
) -> list[dict]:
    """List all available widgets for the given tenant."""
    try:
        return call_schema(tenant)
    except Exception as exc:
        logger.error(f"Error listing widgets: {exc}")
        raise
