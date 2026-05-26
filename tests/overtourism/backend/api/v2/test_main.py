# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient
from overtourism.backend.api.v2.main import create_app


def test_create_app_includes_extra_routers_and_metadata(handler) -> None:
    extra_router = APIRouter()

    @extra_router.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    app = create_app(
        handler,
        title="Custom API",
        version="9.9.9",
        description="Custom description",
        extra_routers=[extra_router],
    )

    with TestClient(app) as client:
        openapi_response = client.get("/openapi.json")
        ping_response = client.get("/ping")

    assert openapi_response.status_code == 200
    assert openapi_response.json()["info"] == {
        "title": "Custom API",
        "version": "9.9.9",
        "description": "Custom description",
    }
    assert ping_response.status_code == 200
    assert ping_response.json() == {"status": "ok"}


def test_create_app_does_not_register_overtourism_data_routes_by_default(
    handler,
) -> None:
    app = create_app(handler)

    assert "/api/v2/{tenant}/data/overtourism/indexes/categories" not in {
        route.path for route in app.routes
    }
