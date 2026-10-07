# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import requests
from fastapi.testclient import TestClient
from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings
from overtourism.backend.main import create_app
from sqlalchemy.exc import SQLAlchemyError


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
        "overtourism.backend.utils.executor_utils.requests.get",
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
        "overtourism.backend.utils.executor_utils.requests.get",
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
        "overtourism.backend.utils.executor_utils.requests.get",
        fail_to_reach_layer_3,
    )
    app = _app_with_auth_enabled(handler)

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_backend_readiness_uses_model_backend_basic_auth_when_configured(
    handler,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "overtourism.backend.utils.executor_utils.MODEL_BACKEND_USER",
        "model-user",
    )
    monkeypatch.setattr(
        "overtourism.backend.utils.executor_utils.MODEL_BACKEND_PASSWORD",
        "model-password",
    )
    captured_request = {}

    def fake_get(url: str, **kwargs):
        captured_request["auth"] = kwargs.get("auth")
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(
        "overtourism.backend.utils.executor_utils.requests.get",
        fake_get,
    )
    app = _app_with_auth_enabled(handler)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert captured_request["auth"] == ("model-user", "model-password")
