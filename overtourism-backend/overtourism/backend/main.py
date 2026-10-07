# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import typing
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overtourism.backend.api.routes.evaluation import evaluation_router
from overtourism.backend.api.routes.parameters import configuration_router
from overtourism.backend.api.routes.problem import problem_router
from overtourism.backend.api.routes.proposal import proposal_router
from overtourism.backend.api.routes.scenario import scenario_router
from overtourism.backend.api.routes.session import session_router
from overtourism.backend.api.routes.territory import territory_router
from overtourism.backend.auth.api.router import auth_router
from overtourism.backend.handler import init_handler
from overtourism.backend.health.checks import model_backend_is_ready, store_is_ready
from overtourism.backend.health.router import create_health_router
from overtourism.backend.utils.config import (
    APP_VERSION,
    BASE_ROUTE,
)
from overtourism.backend.utils.exceptions import install_exception_handlers
from overtourism.backend.utils.logging_config import service_log_format

if typing.TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from overtourism.backend.handler import Handler
    from overtourism.dt_manager.session.manager import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=service_log_format("backend-api", APP_VERSION),
    handlers=[logging.StreamHandler()],
)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _run_session_cleanup(
    session_manager: SessionManager,
    stop_event: Event,
    interval: float,
) -> None:
    while not stop_event.is_set():
        try:
            deleted_count = session_manager.delete_expired_sessions()
            if deleted_count:
                logger.info("Expired sessions cleaned: %s", deleted_count)
        except Exception:
            logger.exception("Session cleanup failed")
        if stop_event.wait(interval):
            return


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
    {
        "name": "Territories",
        "description": "List territories available to the current user.",
    },
    {
        "name": "Health",
        "description": "Operational liveness and readiness probes.",
    },
]


def create_app(
    handler: Handler,
    *,
    title: str = "Digital Twin API",
    version: str = APP_VERSION,
    description: str = "Reusable API for digital twin workflows",
    extra_routers: list[APIRouter] | None = None,
    include_problem_router: bool = True,
    include_proposal_router: bool = True,
    include_scenario_router: bool = True,
) -> FastAPI:
    """Create a FastAPI app wired to the given handler."""
    init_handler(handler)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        stop_event = Event()
        session_manager = handler.manager.session_manager
        cleanup_thread = Thread(
            target=_run_session_cleanup,
            args=(
                session_manager,
                stop_event,
                session_manager.cleanup_config.session_cleanup_interval_seconds,
            ),
            name="session-scenario-cleanup",
            daemon=True,
        )
        cleanup_thread.start()
        try:
            yield
        finally:
            stop_event.set()
            cleanup_thread.join(timeout=5)
            if cleanup_thread.is_alive():
                logger.warning("Session cleanup thread did not stop before timeout")
            else:
                logger.info("Session cleanup thread stopped successfully")

    app = FastAPI(
        title=title,
        version=version,
        description=description,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    install_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if include_problem_router:
        app.include_router(problem_router)
    if include_proposal_router:
        app.include_router(proposal_router)
    if include_scenario_router:
        app.include_router(scenario_router)
    app.include_router(evaluation_router)
    app.include_router(configuration_router)
    app.include_router(session_router)
    app.include_router(territory_router)
    app.include_router(auth_router, prefix=BASE_ROUTE, tags=["Auth"])
    app.include_router(
        create_health_router(
            lambda: store_is_ready(handler.manager.store) and model_backend_is_ready()
        )
    )

    if extra_routers:
        for router in extra_routers:
            app.include_router(router)

    return app
