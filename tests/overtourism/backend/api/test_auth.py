# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.v1.main import create_app as create_app_v1
from overtourism.backend.api.v2.main import create_app as create_app_v2
from overtourism.backend.auth import jwt as auth_jwt
from overtourism.backend.auth.settings import AuthSettings, get_auth_settings
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


@pytest.fixture
def handler(tmp_path) -> Handler:
    model = SimpleNamespace(name="fake-model", indexes=[])
    evaluator = FakeModelEvaluator(model)
    manager = Manager(
        model=model,
        model_evaluator=evaluator,
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        base_problem_config=BaseConfig(tenant="tenant-alpha"),
    )
    return Handler(manager=manager)


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v1, "/api/v1/auth/me"),
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_returns_unauthenticated_context_when_auth_is_disabled(
    handler,
    app_factory,
    auth_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(enabled=False)

    with TestClient(app) as client:
        response = client.get(auth_path, params={"tenant": "tenant-alpha"})

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "tenant": "tenant-alpha",
        "subject": None,
        "token": None,
        "claims": {},
    }


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v1, "/api/v1/auth/me"),
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_requires_bearer_token_when_auth_is_enabled(
    handler,
    app_factory,
    auth_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )

    with TestClient(app) as client:
        response = client.get(auth_path, params={"tenant": "tenant-alpha"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v1, "/api/v1/auth/me"),
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_returns_authenticated_context_for_matching_tenant(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    app_factory,
    auth_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.dependencies.decode_jwt",
        lambda token, settings: {
            "sub": 101,
            settings.tenant_claim: "tenant-alpha",
            "role": "planner",
        },
    )

    with TestClient(app) as client:
        response = client.get(
            auth_path,
            params={"tenant": "tenant-alpha"},
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "tenant": "tenant-alpha",
        "subject": "101",
        "token": "signed-token",
        "claims": {
            "sub": 101,
            "tenant_id": "tenant-alpha",
            "role": "planner",
        },
    }


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v1, "/api/v1/auth/me"),
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_rejects_missing_required_tenant_claim(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    app_factory,
    auth_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
        tenant_claim="organization_id",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.dependencies.decode_jwt",
        lambda token, settings: {"sub": "user-1"},
    )

    with TestClient(app) as client:
        response = client.get(
            auth_path,
            params={"tenant": "tenant-alpha"},
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Token is missing tenant claim 'organization_id'"
    }


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v1, "/api/v1/auth/me"),
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_rejects_mismatched_token_tenant(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    app_factory,
    auth_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.dependencies.decode_jwt",
        lambda token, settings: {
            "sub": "user-1",
            settings.tenant_claim: "tenant-beta",
        },
    )

    with TestClient(app) as client:
        response = client.get(
            auth_path,
            params={"tenant": "tenant-alpha"},
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Token tenant does not match requested tenant"}


def test_auth_settings_from_env_reads_configured_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_ISSUER", "issuer")
    monkeypatch.setenv("AUTH_AUDIENCE", "audience")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://example.com/.well-known/jwks.json")
    monkeypatch.setenv("AUTH_TENANT_CLAIM", "organization_id")
    monkeypatch.setenv("AUTH_ALGORITHMS", "RS256, ES256")
    monkeypatch.setenv("AUTH_LEEWAY_SECONDS", "45")

    settings = AuthSettings.from_env()

    assert settings == AuthSettings(
        enabled=True,
        issuer="issuer",
        audience="audience",
        jwks_url="https://example.com/.well-known/jwks.json",
        tenant_claim="organization_id",
        algorithms=("RS256", "ES256"),
        leeway_seconds=45,
    )


def test_decode_jwt_requires_jwks_url_when_enabled() -> None:
    with pytest.raises(RuntimeError, match="AUTH_JWKS_URL"):
        auth_jwt.decode_jwt("signed-token", AuthSettings(enabled=True))


@pytest.mark.parametrize(
    ("audience", "issuer", "verify_aud", "verify_iss"),
    [
        (None, None, False, False),
        ("audience", "issuer", True, True),
    ],
)
def test_decode_jwt_uses_the_configured_validation_settings(
    monkeypatch: pytest.MonkeyPatch,
    audience: str | None,
    issuer: str | None,
    verify_aud: bool,
    verify_iss: bool,
) -> None:
    captured: dict[str, Any] = {}

    class FakeSigningKey:
        key = "public-key"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            captured["jwks_token"] = token
            return FakeSigningKey()

    def fake_decode(token: str, signing_key: str, **kwargs: Any) -> dict[str, str]:
        captured["token"] = token
        captured["signing_key"] = signing_key
        captured["kwargs"] = kwargs
        return {"sub": "user-1"}

    monkeypatch.setattr(auth_jwt, "_jwks_client", lambda url: FakeJwksClient())
    monkeypatch.setattr(auth_jwt.jwt, "decode", fake_decode)

    claims = auth_jwt.decode_jwt(
        "signed-token",
        AuthSettings(
            enabled=True,
            issuer=issuer,
            audience=audience,
            jwks_url="https://example.com/.well-known/jwks.json",
            algorithms=("RS256", "ES256"),
            leeway_seconds=45,
        ),
    )

    assert claims == {"sub": "user-1"}
    assert captured == {
        "jwks_token": "signed-token",
        "token": "signed-token",
        "signing_key": "public-key",
        "kwargs": {
            "algorithms": ["RS256", "ES256"],
            "leeway": 45,
            "options": {
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": False,
                "verify_aud": verify_aud,
                "verify_iss": verify_iss,
            },
            **({"audience": audience} if audience is not None else {}),
            **({"issuer": issuer} if issuer is not None else {}),
        },
    }
