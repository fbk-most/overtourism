# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import typing

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overtourism.backend.api.problem import problem_router
from overtourism.backend.api.proposal import proposal_router
from overtourism.backend.api.scenario import scenario_router
from overtourism.backend.api.shared.dependencies import init_handler
from overtourism.backend.api.widget import widget_router
from overtourism.backend.auth.router import auth_router

if typing.TYPE_CHECKING:
    from overtourism.backend.handler import Handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler()],
)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def create_app(
    handler: Handler,
    *,
    title: str = "Overtourism API",
    version: str = "0.1.0",
    description: str = "",
    extra_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Create a FastAPI app wired to the given handler.

    Parameters
    ----------
    handler : Handler
        Backend singletons (problem_manager, viewer, ...).
    title, version, description : str
        OpenAPI metadata.
    extra_routers : list, optional
        Additional APIRouters to include, for example data routes.
    """
    init_handler(handler)

    app = FastAPI(title=title, version=version, description=description)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(scenario_router)
    app.include_router(problem_router)
    app.include_router(widget_router)
    app.include_router(proposal_router)
    app.include_router(auth_router)

    if extra_routers:
        for router in extra_routers:
            app.include_router(router)

    return app
