# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.v1.main import create_app
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


@pytest.fixture
def tenant() -> str:
    return "tenant-alpha"


@pytest.fixture
def manager(tmp_path, tenant: str) -> Manager:
    model = SimpleNamespace(name="fake-model", indexes=[])
    evaluator = FakeModelEvaluator(model)
    return Manager(
        model=model,
        model_evaluator=evaluator,
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        base_problem_config=BaseConfig(tenant=tenant),
    )


@pytest.fixture
def client(manager: Manager, tenant: str) -> TestClient:
    app = create_app(Handler(manager=manager))
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=tenant,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app) as test_client:
        yield test_client


def test_list_problems_filters_by_tenant(
    client: TestClient,
    manager: Manager,
    tenant: str,
) -> None:
    manager.problem_manager.create_problem(
        "tenant-beta-problem",
        tenant="tenant-beta",
        name="Other problem",
        description="Not visible from this tenant",
        extras={},
    )

    response = client.get(f"/api/v1/{tenant}/problems")

    assert response.status_code == 200
    assert [item["problem_id"] for item in response.json()["data"]] == ["default"]


def test_create_problem_stores_path_tenant_and_blocks_other_tenant_reads(
    client: TestClient,
    tenant: str,
) -> None:
    create_response = client.post(
        f"/api/v1/{tenant}/problems",
        json={
            "problem_name": "Lake Cleanup",
            "problem_description": "Reduce visitor pressure",
        },
    )

    assert create_response.status_code == 200
    assert create_response.json() == {
        "message": "Problem created successfully",
        "problem_id": "lake-cleanup",
    }

    same_tenant = client.get(f"/api/v1/{tenant}/problems/lake-cleanup")
    other_tenant = client.get("/api/v1/tenant-beta/problems/lake-cleanup")

    assert same_tenant.status_code == 200
    assert same_tenant.json()["problem_id"] == "lake-cleanup"
    assert other_tenant.status_code == 404
