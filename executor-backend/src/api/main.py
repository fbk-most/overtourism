# SPDX-License-Identifier: Apache-2.0
"""FastAPI entry point — Layer 5 REST API over the Fazzon/Molveno computation backends.

Run with::

    uv run fastapi dev overtourism/api/main.py
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.api.logging_config import service_log_format
from src.api.routes import router

APP_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format=service_log_format("executor-backend", APP_VERSION),
    handlers=[logging.StreamHandler()],
)


def _get_cors_allowed_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    return [
        origin.strip() for origin in configured_origins.split(",") if origin.strip()
    ]


def create_app() -> FastAPI:
    application = FastAPI(
        title="Overtourism Digital Twin API",
        version=APP_VERSION,
        description="REST layer over the CDT computation backends.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    application.include_router(health_router)
    return application


app = create_app()
