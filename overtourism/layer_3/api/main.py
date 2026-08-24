# SPDX-License-Identifier: Apache-2.0
"""FastAPI entry point — Layer 5 REST API over the Fazzon/Molveno computation backends.

Run with::

    uv run fastapi dev overtourism/api/main.py
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overtourism.layer_3.api.routes import router

app = FastAPI(
    title="Overtourism Digital Twin API",
    version="0.1.0",
    description="REST layer over the Fazzon/Molveno computation backends (Layer 3).",
)

# Permissive dev CORS — mirrors overtourism.OLD/backend/api/main.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
