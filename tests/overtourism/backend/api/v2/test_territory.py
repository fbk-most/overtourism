# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.main import create_app
from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings


def test_list_territorys_returns_model_keys_when_auth_is_disabled(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(enabled=False)
    monkeypatch.setattr(
        "overtourism.backend.api.v2.territory.list_models",
        lambda: [{"key": "territory-alpha"}, {"key": "territory-beta"}],
    )

    with TestClient(app) as client:
        response = client.get("/api/v2/default/territorys")

    assert response.status_code == 200
    assert response.json() == ["territory-alpha", "territory-beta"]


def test_list_territorys_filters_model_keys_to_authenticated_user_territorys(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {
            "sub": "user-1",
            settings.territory_claim: ["territory-beta", "territory-alpha"],
        },
    )
    monkeypatch.setattr(
        "overtourism.backend.api.v2.territory.list_models",
        lambda: [
            {"key": "territory-alpha"},
            {"key": "territory-gamma"},
            {"key": "territory-beta"},
        ],
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/default/territorys",
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json() == ["territory-alpha", "territory-beta"]


def test_list_territorys_returns_no_territorys_when_authenticated_claim_is_missing(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {"sub": "user-1"},
    )
    monkeypatch.setattr(
        "overtourism.backend.api.v2.territory.list_models",
        lambda: [{"key": "territory-alpha"}],
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/default/territorys",
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json() == []
