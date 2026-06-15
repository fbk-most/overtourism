# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import FastAPI

from overtourism.backend.api.v1.main import create_app
from overtourism.backend.handler import Handler
from overtourism.overtourism.backend_extension.api.v1.data import data_router
from overtourism.overtourism.molveno.molveno_runner import arrange_data as _arrange_data
from overtourism.overtourism.molveno.setup import data_loader, manager_molveno, viewer


def build_handler() -> Handler:
    """Build the overtourism v1 backend handler and its collaborators."""
    return Handler(
        manager=manager_molveno,
        arrange_data_fn=lambda data, params=None, as_snapshot=False: _arrange_data(
            data,
            api_version="v1",
            as_snapshot=as_snapshot,
        ),
        viewer=viewer,
        prepare_values_fn=viewer.prepare_values,
        data_loader=data_loader,
    )


def build_app() -> FastAPI:
    """Build the FastAPI application for the overtourism v1 backend."""
    return create_app(
        build_handler(),
        title="AIxPA Over-Tourism API",
        version="0.1.0",
        description="API for tourism indices in Trentino",
        extra_routers=[data_router],
    )


app = build_app()
