# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.main import create_app
from overtourism.backend.auth.settings import AuthSettings, get_auth_settings


def test_list_tenants_returns_model_keys_when_auth_is_disabled(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(enabled=False)
    monkeypatch.setattr(
        "overtourism.backend.api.v2.tenant.list_models",
        lambda: [{"key": "tenant-alpha"}, {"key": "tenant-beta"}],
    )

    with TestClient(app) as client:
        response = client.get("/api/v2/default/tenants")

    assert response.status_code == 200
    assert response.json() == ["tenant-alpha", "tenant-beta"]


def test_list_tenants_filters_model_keys_to_authenticated_user_tenants(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.dependencies.decode_jwt",
        lambda token, settings: {
            "sub": "user-1",
            settings.tenant_claim: ["tenant-beta", "tenant-alpha"],
        },
    )
    monkeypatch.setattr(
        "overtourism.backend.api.v2.tenant.list_models",
        lambda: [
            {"key": "tenant-alpha"},
            {"key": "tenant-gamma"},
            {"key": "tenant-beta"},
        ],
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/default/tenants",
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json() == ["tenant-alpha", "tenant-beta"]


def test_list_tenants_returns_no_tenants_when_authenticated_claim_is_missing(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.dependencies.decode_jwt",
        lambda token, settings: {"sub": "user-1"},
    )
    monkeypatch.setattr(
        "overtourism.backend.api.v2.tenant.list_models",
        lambda: [{"key": "tenant-alpha"}],
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/default/tenants",
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json() == []
