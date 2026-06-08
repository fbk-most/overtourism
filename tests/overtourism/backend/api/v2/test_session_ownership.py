# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from overtourism.backend.api.v2 import session as session_api
from overtourism.backend.api.v2.main import create_app
from overtourism.backend.api.v2.session_ownership import (
    SessionOwnershipStore,
    claim_session_ownership,
    resolve_session_owner_id,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


@pytest.fixture
def ownership_store(tmp_path) -> SessionOwnershipStore:
    return SessionOwnershipStore(tmp_path / "session_ownership.sqlite")


@pytest.fixture
def handler(tmp_path, ownership_store: SessionOwnershipStore) -> Handler:
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
    return Handler(manager=manager, session_ownership_store=ownership_store)


def test_resolve_session_owner_prefers_email_then_subject_then_anonymous() -> None:
    tenant = "tenant-alpha"

    assert (
        resolve_session_owner_id(
            AuthContext(
                authenticated=True,
                tenant=tenant,
                subject="subject-owner",
                token="token",
                claims={"email": "owner@example.com", "sub": "subject-owner"},
            ),
            tenant,
        )
        == "owner@example.com"
    )

    assert (
        resolve_session_owner_id(
            AuthContext(
                authenticated=True,
                tenant=tenant,
                subject="subject-owner",
                token="token",
                claims={"sub": "subject-owner"},
            ),
            tenant,
        )
        == "subject-owner"
    )

    assert (
        resolve_session_owner_id(
            AuthContext(
                authenticated=False,
                tenant=tenant,
                subject=None,
                token=None,
                claims={},
            ),
            tenant,
        )
        == "anonymous:tenant-alpha"
    )


def test_session_ownership_store_claims_reads_and_cleans_up_sessions(
    handler: Handler,
) -> None:
    problem_id = handler.manager.base_problem_config.problem_id
    tenant = handler.manager.base_problem_config.tenant

    handler.session_ownership_store.claim_session(
        tenant,
        problem_id,
        "session-1",
        "owner@example.com",
    )

    assert (
        handler.session_ownership_store.read_session_owner(
            tenant,
            problem_id,
            "session-1",
        )
        == "owner@example.com"
    )
    assert handler.session_ownership_store.list_session_ids(
        tenant,
        problem_id,
        "owner@example.com",
    ) == ["session-1"]

    handler.session_ownership_store.delete_session(
        tenant,
        problem_id,
        "session-1",
    )
    assert (
        handler.session_ownership_store.read_session_owner(
            tenant,
            problem_id,
            "session-1",
        )
        is None
    )


def test_claim_session_ownership_rejects_cross_user_claims(handler: Handler) -> None:
    tenant = handler.manager.base_problem_config.tenant
    problem_id = handler.manager.base_problem_config.problem_id

    handler.session_ownership_store.claim_session(
        tenant,
        problem_id,
        "session-2",
        "owner@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        claim_session_ownership(
            handler,
            tenant,
            problem_id,
            "session-2",
            AuthContext(
                authenticated=True,
                tenant=tenant,
                subject="other-owner",
                token="token",
                claims={"email": "other@example.com"},
            ),
        )
    assert exc_info.value.status_code == 404


def test_session_routes_reject_other_users_but_keep_owner_access(
    handler: Handler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = handler.manager.base_problem_config.tenant
    problem_id = handler.manager.base_problem_config.problem_id
    app = create_app(handler)

    def owner_a_context() -> AuthContext:
        return AuthContext(
            authenticated=True,
            tenant=tenant,
            subject="owner-a-subject",
            token="token-a",
            claims={"email": "owner-a@example.com", "sub": "owner-a-subject"},
        )

    def owner_b_context() -> AuthContext:
        return AuthContext(
            authenticated=True,
            tenant=tenant,
            subject="owner-b-subject",
            token="token-b",
            claims={"email": "owner-b@example.com", "sub": "owner-b-subject"},
        )

    app.dependency_overrides[get_auth_context] = owner_a_context
    monkeypatch.setattr(
        session_api, "uuid4", lambda: SimpleNamespace(hex="session-owned")
    )

    with TestClient(app) as client:
        create_response = client.post(
            f"/api/v2/{tenant}/sessions",
            params={"problem_id": problem_id},
            json={"metadata": {}},
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        assert (
            handler.session_ownership_store.read_session_owner(
                tenant,
                problem_id,
                session_id,
            )
            == "owner-a@example.com"
        )

        app.dependency_overrides[get_auth_context] = owner_b_context
        assert (
            client.get(
                f"/api/v2/{tenant}/sessions/{session_id}",
                params={"problem_id": problem_id},
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v2/{tenant}/sessions",
                params={"problem_id": problem_id},
            ).json()
            == []
        )

        app.dependency_overrides[get_auth_context] = owner_a_context
        assert (
            client.get(
                f"/api/v2/{tenant}/sessions/{session_id}",
                params={"problem_id": problem_id},
            ).status_code
            == 200
        )
