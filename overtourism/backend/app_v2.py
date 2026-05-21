# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from overtourism.backend.api.v2.data import data_router
from overtourism.backend.api.v2.main import create_app
from overtourism.backend.data.catalog import MOLVENO_SIM_INDEXES
from overtourism.backend.data.loader import OvertourismIndexesLoader
from overtourism.backend.data.viewer.viewer import ModelViewer
from overtourism.backend.handler import Handler
from overtourism.overtourism.molveno_runner import arrange_data
from overtourism.overtourism.setup import manager

viewer = ModelViewer(MOLVENO_SIM_INDEXES)
data_loader = OvertourismIndexesLoader(
    str(Path(__file__).parent / "model" / "data" / "index_data")
)


def build_handler() -> Handler:
    """Build the backend handler and its collaborators."""
    return Handler(
        manager=manager,
        arrange_data_fn=arrange_data,
        viewer=viewer,
        prepare_values_fn=viewer.prepare_values,
        data_loader=data_loader,
    )


def build_app() -> FastAPI:
    """Build the FastAPI application for the backend."""
    return create_app(
        build_handler(),
        extra_routers=[data_router],
    )


app = build_app()
