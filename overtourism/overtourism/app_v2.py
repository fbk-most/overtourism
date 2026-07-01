# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os

from fastapi import FastAPI

from overtourism.backend.api.v2.main import create_app
from overtourism.overtourism.backend_extension.api.v2.data import data_router
from overtourism.overtourism.backend_extension.api.v2.widget import widget_router
from overtourism.overtourism.molveno.setup import build_handler
from overtourism.overtourism.platform import download_index_data


def build_app() -> FastAPI:
    """Build the FastAPI application for the overtourism v2 backend."""
    return create_app(
        build_handler(),
        title="Overtourism API",
        description="API for tourism indices in Trentino",
        extra_routers=[data_router, widget_router],
    )


# Whether execute standalone, with data already prepared
standalone_mode = os.getenv("DT_OVERTURISM_STANDALONE_MODE", "true").lower() == "false"
if not standalone_mode:
    download_index_data()

app = build_app()
