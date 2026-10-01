# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.main import create_app as create_app_v2
from overtourism.backend.auth.identity.sql_repository import SQLUserRepository
from overtourism.backend.auth.identity.user_manager import UserManager
from overtourism.backend.auth.identity.users import UserRole
from overtourism.backend.auth.tokens import jwt as auth_jwt
from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.overtourism.backend_extension.api.v2 import indexes as indexes_api
from overtourism.overtourism.backend_extension.api.v2.indexes import indexes_router
from overtourism.overtourism.backend_extension.api.v2.problem import (
    problem_router as overtourism_problem_router,
)
from overtourism.overtourism.backend_extension.api.v2.proposal import (
    proposal_router as overtourism_proposal_router,
)
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType


@pytest.fixture
def handler(tmp_path) -> Handler:
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
    )
    store = cast(SQLStore, manager.store)
    repository = SQLUserRepository(store.engine, store.session_factory)
    user_manager = UserManager(repository)
    for subject in ("101", "user-1"):
        user = user_manager.create_user(
            identifier=f"{subject}@example.org",
            role=UserRole.VIEWER,
            territories=["territory-alpha"],
        )
        repository.save_user(replace(user, subject=subject))
    user_manager.reload()
    return Handler(manager=manager, user_manager=user_manager)


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
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
        response = client.get(auth_path)

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "territory": None,
        "subject": None,
        "user_id": None,
        "role": None,
        "is_global_admin": False,
        "territories": [],
    }


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
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
        response = client.get(auth_path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_returns_authenticated_context_and_database_territory(
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
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {"sub": 101},
    )

    with TestClient(app) as client:
        response = client.get(
            auth_path,
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    user_data = response.json()
    assert user_data["authenticated"] is True
    assert user_data["territory"] == "territory-alpha"
    assert user_data["subject"] == "101"
    assert user_data["user_id"]
    assert user_data["role"] == "viewer"
    assert user_data["is_global_admin"] is False
    assert user_data["territories"] == ["territory-alpha"]


@pytest.mark.parametrize(
    ("app_factory", "problems_path"),
    [
        (create_app_v2, "/api/v2/territory-alpha/problems"),
    ],
)
@pytest.mark.parametrize("tenant_claim", [None, "territory-beta"])
def test_territory_scoped_routes_allow_database_assignment_without_territory_claim(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    app_factory,
    problems_path: str,
    tenant_claim: str | None,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    claims = {"sub": "user-1"}
    if tenant_claim is not None:
        claims["tenant_id"] = tenant_claim
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: claims,
    )

    with TestClient(app) as client:
        response = client.get(
            problems_path,
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("app_factory", "route_path"),
    [
        (create_app_v2, "/api/v2/territory-gamma/problems"),
        (create_app_v2, "/api/v2/territory-gamma/proposals"),
        (create_app_v2, "/api/v2/territory-gamma/scenarios"),
        (create_app_v2, "/api/v2/territory-gamma/evaluations"),
        (create_app_v2, "/api/v2/territory-gamma/configuration"),
        (create_app_v2, "/api/v2/territory-gamma/sessions"),
    ],
)
def test_territory_scoped_routes_reject_database_unassigned_territory_despite_jwt_claim(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    app_factory,
    route_path: str,
) -> None:
    app = app_factory(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {
            "sub": "user-1",
            "tenant_id": "territory-gamma",
        },
    )

    with TestClient(app) as client:
        response = client.get(
            route_path,
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "User is not assigned to this territory"}


def test_global_admin_can_access_unassigned_application_territories(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = cast(SQLStore, handler.manager.store)
    repository = SQLUserRepository(store.engine, store.session_factory)
    user_manager = UserManager(repository)
    admin = user_manager.create_user(
        identifier="global-admin@example.org",
        role=UserRole.ADMIN,
        territories=[],
    )
    repository.save_user(replace(admin, subject="global-admin"))
    user_manager.reload()
    handler.user_manager = user_manager

    app = create_app_v2(handler)
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {"sub": "global-admin"},
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/territory-gamma/problems",
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200


def test_overtourism_routes_use_db_scope_but_indexes_require_only_a_valid_jwt(
    handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app_v2(
        handler,
        include_problem_router=False,
        include_proposal_router=False,
        extra_routers=[
            overtourism_problem_router,
            overtourism_proposal_router,
            indexes_router,
        ],
    )
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwks_url="https://example.com/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {"sub": "unregistered-user"},
    )
    monkeypatch.setattr(indexes_api, "_REGISTRY", {})

    with TestClient(app) as client:
        problem_response = client.get(
            "/api/v2/territory-gamma/problems",
            headers={"Authorization": "Bearer signed-token"},
        )
        proposal_response = client.get(
            "/api/v2/territory-gamma/proposals",
            headers={"Authorization": "Bearer signed-token"},
        )
        index_response = client.get(
            "/api/v2/default/indexes/get-index-list",
            headers={"Authorization": "Bearer signed-token"},
        )
        unauthenticated_index_response = client.get(
            "/api/v2/default/indexes/get-index-list"
        )

    assert problem_response.status_code == 403
    assert proposal_response.status_code == 403
    assert index_response.status_code == 200
    assert unauthenticated_index_response.status_code == 401


@pytest.mark.parametrize(
    ("app_factory", "auth_path"),
    [
        (create_app_v2, "/api/v2/auth/me"),
    ],
)
def test_auth_me_does_not_require_tenant_claim(
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
        "overtourism.backend.auth.tokens.dependencies.decode_jwt",
        lambda token, settings: {"sub": "user-1"},
    )

    with TestClient(app) as client:
        response = client.get(
            auth_path,
            headers={"Authorization": "Bearer signed-token"},
        )

    assert response.status_code == 200
    assert response.json()["territory"] == "territory-alpha"
    assert response.json()["subject"] == "user-1"


def test_auth_settings_from_env_reads_configured_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_ISSUER", "issuer")
    monkeypatch.setenv("AUTH_AUDIENCE", "audience")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://example.com/.well-known/jwks.json")
    monkeypatch.setenv("AUTH_ALGORITHMS", "RS256, ES256")
    monkeypatch.setenv("AUTH_LEEWAY_SECONDS", "45")

    settings = AuthSettings.from_env()

    assert settings == AuthSettings(
        enabled=True,
        issuer="issuer",
        audience="audience",
        jwks_url="https://example.com/.well-known/jwks.json",
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
