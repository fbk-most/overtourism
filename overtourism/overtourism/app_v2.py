# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import FastAPI

from overtourism.backend.api.v2.main import create_app
from overtourism.backend.handler import Handler
from overtourism.overtourism.api.v2.data import data_router
from overtourism.overtourism.api.v2.problem import problem_router
from overtourism.overtourism.api.v2.problem_extras import prepare_problem_extras
from overtourism.overtourism.api.v2.widget import widget_router
from overtourism.overtourism.molveno_runner import arrange_data as _arrange_data
from overtourism.overtourism.setup import data_loader, manager, viewer


def build_handler() -> Handler:
    """Build the overtourism v2 backend handler and its collaborators."""
    return Handler(
        manager=manager,
        get_widgets_fn=viewer.get_widgets,
        get_widget_ids_by_groups_fn=viewer.get_widget_ids_by_groups,
        prepare_problem_extras_fn=lambda extras,
        payload,
        current_extras=None: prepare_problem_extras(
            extras,
            payload,
            current_extras,
            viewer=viewer,
        ),
        arrange_data_fn=lambda data, params=None: _arrange_data(
            data,
            api_version="v2",
            fields=params,
        ),
        viewer=viewer,
        prepare_values_fn=viewer.prepare_values,
        data_loader=data_loader,
    )


def build_app() -> FastAPI:
    """Build the FastAPI application for the overtourism v2 backend."""
    return create_app(
        build_handler(),
        title="Overtourism API",
        description="API for tourism indices in Trentino",
        include_problem_router=False,
        extra_routers=[problem_router, data_router, widget_router],
    )


app = build_app()
