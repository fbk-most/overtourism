# SPDX-License-Identifier: Apache-2.0
"""FastAPI entry point — Layer 5 REST API over the Fazzon/Molveno computation backends.

Run with::

    uv run fastapi dev overtourism/api/main.py
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overtourism.layer_3.api.health import router as health_router
from overtourism.layer_3.api.logging_config import service_log_format
from overtourism.layer_3.api.routes import router

APP_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format=service_log_format("layer-3-models", APP_VERSION),
    handlers=[logging.StreamHandler()],
)

app = FastAPI(
    title="Overtourism Digital Twin API",
    version=APP_VERSION,
    description="REST layer over the Fazzon/Molveno computation backends (Layer 3).",
)

# Permissive development CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(health_router)
