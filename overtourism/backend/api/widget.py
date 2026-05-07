# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends

from overtourism.backend.api.dependencies import get_managers
from overtourism.backend.managers import Managers
from overtourism.backend.shared.models.widgets import Widgets
from overtourism.backend.shared.utils import BASE_ROUTE

logger = logging.getLogger(__name__)

widget_router = APIRouter(prefix=BASE_ROUTE)


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
    mgrs: Managers = Depends(get_managers),
) -> Widgets:
    try:
        if mgrs.viewer is not None:
            return Widgets(widgets=mgrs.viewer.get_widgets({}, language=language))
        return Widgets(widgets={})
    except Exception as e:
        logger.error(f"Error listing widgets: {e}")
        raise
