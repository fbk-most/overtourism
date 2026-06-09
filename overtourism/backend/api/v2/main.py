# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import typing

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overtourism.backend.api.shared.dependencies import init_handler
from overtourism.backend.api.shared.exceptions import install_exception_handlers
from overtourism.backend.api.v2.config import APP_VERSION, TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.evaluation import evaluation_router
from overtourism.backend.api.v2.problem import problem_router
from overtourism.backend.api.v2.proposal import proposal_router
from overtourism.backend.api.v2.scenario import scenario_router
from overtourism.backend.api.v2.session import session_router
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

OPENAPI_TAGS = [
    {
        "name": "Problems",
        "description": "Create and manage optimization problems.",
    },
    {
        "name": "Proposals",
        "description": "Manage proposals linked to problems.",
    },
    {
        "name": "Sessions",
        "description": "Create and manage sessions.",
    },
    {
        "name": "Scenarios",
        "description": "Inspect and update scenarios within a problem.",
    },
    {
        "name": "Evaluations",
        "description": "Run and inspect scenario evaluations.",
    },
    {
        "name": "Auth",
        "description": "Authentication and current user context.",
    },
]


def create_app(
    handler: Handler,
    *,
    title: str = "Digital Twin API",
    version: str = APP_VERSION,
    description: str = "Reusable API for digital twin workflows",
    extra_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Create a FastAPI app wired to the given handler."""
    init_handler(handler)

    app = FastAPI(
        title=title,
        version=version,
        description=description,
        openapi_tags=OPENAPI_TAGS,
    )
    install_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(problem_router)
    app.include_router(proposal_router)
    app.include_router(scenario_router)
    app.include_router(evaluation_router)
    app.include_router(session_router)
    app.include_router(auth_router, prefix=TENANT_ROUTE_PREFIX, tags=["Auth"])

    if extra_routers:
        for router in extra_routers:
            app.include_router(router)

    return app
