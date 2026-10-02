# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import requests
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings
from overtourism.backend.main import create_app


def _app_with_auth_enabled(handler):
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    return app


def test_backend_health_probes_are_public_and_report_live_and_ready(
    handler,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "overtourism.backend.health.checks.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )
    app = _app_with_auth_enabled(handler)

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}


def test_backend_readiness_is_unavailable_when_database_cannot_be_reached(
    handler,
    monkeypatch,
) -> None:
    def fail_to_connect():
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        "overtourism.backend.health.checks.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )
    monkeypatch.setattr(handler.manager.store.engine, "connect", fail_to_connect)
    app = _app_with_auth_enabled(handler)

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_backend_readiness_is_unavailable_when_layer_3_is_unreachable(
    handler,
    monkeypatch,
) -> None:
    def fail_to_reach_layer_3(*args, **kwargs):
        raise requests.ConnectionError("layer 3 unavailable")

    monkeypatch.setattr(
        "overtourism.backend.health.checks.requests.get",
        fail_to_reach_layer_3,
    )
    app = _app_with_auth_enabled(handler)

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
