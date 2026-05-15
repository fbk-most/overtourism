# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends

from overtourism.backend.api.shared.dependencies import get_handler
from overtourism.backend.api.shared.models.widgets import Widgets
from overtourism.backend.api.shared.utils import TENANT_ROUTE_PREFIX
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.handler import Handler

logger = logging.getLogger(__name__)

widget_router = APIRouter(
    prefix=TENANT_ROUTE_PREFIX,
    dependencies=[Depends(get_auth_context)],
)


@widget_router.get(
    "/widgets",
    response_model=Widgets,
    responses={
        500: {"description": "View manager error"},
        200: {"description": "Widget list"},
    },
)
async def list_widgets(
    language: Literal["it", "en"] = "it",
    handler: Handler = Depends(get_handler),
) -> Widgets:
    try:
        if handler.viewer is not None:
            return Widgets(widgets=handler.viewer.get_widgets({}, language=language))
        return Widgets(widgets={})
    except Exception as e:
        logger.error(f"Error listing widgets: {e}")
        raise
