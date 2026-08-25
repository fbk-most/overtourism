# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import FastAPI

from overtourism.backend.api.main import create_app
from overtourism.overtourism.backend_extension.api.v2.indexes import indexes_router
from overtourism.overtourism.backend_extension.api.v2.problem import problem_router
from overtourism.overtourism.backend_extension.api.v2.proposal import proposal_router
from overtourism.overtourism.setup import build_handler


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
            indexes_router,
        ],
    )


app = build_app()
