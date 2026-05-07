# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends

from overtourism.backend.api.dependencies import get_managers
from overtourism.backend.data.loader import OvertourismIndexesLoader
from overtourism.backend.managers import Managers
from overtourism.backend.shared.utils import BASE_ROUTE

logger = logging.getLogger(__name__)

data_router = APIRouter(prefix=f"{BASE_ROUTE}/data")


def _loader(managers: Managers = Depends(get_managers)) -> OvertourismIndexesLoader:
    if managers.data_loader is None:
        raise RuntimeError("Data loader not configured")
    return managers.data_loader


@data_router.get(
    "/overtourism/indexes/categories",
    response_model=dict,
    responses={
        500: {"description": "Data loader error"},
        200: {"description": "Overtourism categories list"},
    },
)
async def get_overtourism_categories_list(
    language: Literal["it", "en"] = "it",
    loader: OvertourismIndexesLoader = Depends(_loader),
) -> dict:
    try:
        return loader.get_categories(language=language)
    except Exception as e:
        logger.error(f"Error getting overtourism categories list: {e}")
        raise


@data_router.get(
    "/overtourism/indexes/list",
    response_model=dict,
    responses={
        500: {"description": "Data loader error"},
        200: {"description": "Overtourism indexes list"},
    },
)
async def get_overtourism_indexes_list(
    category: str = "",
    language: Literal["it", "en"] = "it",
    loader: OvertourismIndexesLoader = Depends(_loader),
) -> dict:
    try:
        return loader.get_list(category=category, language=language)
    except Exception as e:
        logger.error(f"Error getting overtourism indexes list: {e}")
        raise


@data_router.get(
    "/overtourism/indexes/data",
    response_model=dict,
    responses={
        500: {"description": "Data loader error"},
        404: {"description": "Data not found"},
        200: {"description": "Overtourism index data"},
    },
)
async def get_overtourism_indexes_data(
    dataframe: str,
    loader: OvertourismIndexesLoader = Depends(_loader),
) -> dict:
    try:
        return loader.get_dataframe(dataframe)
    except Exception as e:
        logger.error(f"Error getting overtourism indexes data: {e}")
        raise


@data_router.get(
    "/overtourism/indexes/map",
    response_model=dict,
    responses={
        500: {"description": "Data loader error"},
        404: {"description": "Data not found"},
        200: {"description": "Overtourism index map"},
    },
)
async def get_overtourism_indexes_map(
    map: str,
    loader: OvertourismIndexesLoader = Depends(_loader),
) -> dict:
    try:
        return loader.get_map(map)
    except Exception as e:
        logger.error(f"Error getting overtourism indexes map: {e}")
        raise
