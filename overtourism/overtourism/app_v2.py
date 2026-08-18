# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os

from fastapi import FastAPI

from overtourism.backend.api.v2.main import create_app
from overtourism.overtourism.backend_extension.api.v2.data import data_router
from overtourism.overtourism.backend_extension.api.v2.indexes import indexes_router
from overtourism.overtourism.backend_extension.api.v2.problem import problem_router
from overtourism.overtourism.backend_extension.api.v2.proposal import proposal_router
from overtourism.overtourism.backend_extension.api.v2.widget import widget_router
from overtourism.overtourism.molveno.setup import build_handler
from overtourism.overtourism.platform import download_index_data_v2


def build_app() -> FastAPI:
    """Build the FastAPI application for the overtourism v2 backend."""
    return create_app(
        build_handler(),
        title="Overtourism API",
        description="API for tourism indices in Trentino",
        include_problem_router=False,
        include_proposal_router=False,
        extra_routers=[
            problem_router,
            proposal_router,
            data_router,
            indexes_router,
            widget_router,
        ],
    )


# Whether execute standalone, with data already prepared
standalone_mode = os.getenv("DT_OVERTURISM_STANDALONE_MODE", "true").lower() == "true"

if not standalone_mode:
    # download_index_data()
    download_index_data_v2()

app = build_app()
