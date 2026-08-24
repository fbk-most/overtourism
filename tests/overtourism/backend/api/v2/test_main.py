# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from overtourism.backend.api.main import create_app


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


def test_create_app_does_not_register_overtourism_extension_routes_by_default(
    handler,
) -> None:
    app = create_app(handler)

    paths = {route.path for route in app.routes}

    assert "/api/v2/{tenant}/data/overtourism/indexes/categories" not in paths
    assert "/api/v2/{tenant}/widgets" not in paths


def test_create_app_exposes_bearer_auth_in_openapi(handler) -> None:
    app = create_app(handler)

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert openapi["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert openapi["paths"]["/api/v2/{tenant}/problems"]["get"]["security"] == [
        {"BearerAuth": []}
    ]
    assert openapi["paths"]["/api/v2/{tenant}/auth/me"]["get"]["security"] == [
        {"BearerAuth": []}
    ]


def test_create_app_groups_routes_by_domain_tags_in_openapi(handler) -> None:
    app = create_app(handler)

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert openapi["tags"] == [
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
    assert openapi["paths"]["/api/v2/{tenant}/problems"]["get"]["tags"] == ["Problems"]
    assert openapi["paths"]["/api/v2/{tenant}/proposals"]["get"]["tags"] == [
        "Proposals"
    ]
    assert openapi["paths"]["/api/v2/{tenant}/sessions"]["post"]["tags"] == ["Sessions"]
    assert openapi["paths"]["/api/v2/{tenant}/scenarios"]["get"]["tags"] == [
        "Scenarios"
    ]
    assert openapi["paths"]["/api/v2/{tenant}/evaluations"]["post"]["tags"] == [
        "Evaluations"
    ]
    assert openapi["paths"]["/api/v2/{tenant}/auth/me"]["get"]["tags"] == ["Auth"]
