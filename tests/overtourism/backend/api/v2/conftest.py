# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.v2.main import create_app
from overtourism.backend.api.v2.session_ownership import SessionOwnershipStore
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.handler import Handler
from overtourism.overtourism.setup.bootstrap import bootstrap_entities
from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.overtourism.registry import (
    ExecutionManagerRegistry,
    ModelExecutionService,
)
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


def _normalize_output(
    data: Any,
    as_snapshot: bool = False,
    params: list[str] | None = None,
) -> dict[str, Any]:
    if hasattr(data, "to_dict"):
        normalized = data.to_dict()
    elif hasattr(data, "to_snapshot"):
        normalized = data.to_snapshot()
    else:
        normalized = data
    if params is None or not isinstance(normalized, dict):
        return normalized
    return {key: normalized[key] for key in params if key in normalized}


@dataclass
class RecordingViewer:
    widget_calls: list[tuple[dict[str, Any], str]] = field(default_factory=list)
    group_calls: list[list[str]] = field(default_factory=list)

    def get_widgets(
        self,
        values: dict[str, Any],
        language: str = "it",
    ) -> dict[str, Any]:
        snapshot = dict(values)
        self.widget_calls.append((snapshot, language))
        return {"summary": {"language": language, "values": snapshot}}

    def get_widget_ids_by_groups(self, groups: list[str]) -> list[str]:
        normalized_groups = list(groups)
        self.group_calls.append(normalized_groups)
        return [f"{group}-widget" for group in normalized_groups]


@pytest.fixture
def tenant() -> str:
    return "tenant-alpha"


@pytest.fixture
def viewer() -> RecordingViewer:
    return RecordingViewer()


@pytest.fixture
def session_ownership_store(tmp_path) -> SessionOwnershipStore:
    return SessionOwnershipStore(tmp_path / "session_ownership.sqlite")


@pytest.fixture
def manager(tmp_path, tenant: str) -> Manager:
    return Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        names_cfg=BootstrapConfig(tenant=tenant),
    )


@pytest.fixture
def execution_manager_registry(
    manager: Manager, tenant: str
) -> ExecutionManagerRegistry:
    model = SimpleNamespace(name="fake-model", indexes=[])
    evaluator = FakeModelEvaluator(model)
    registry = ExecutionManagerRegistry()
    registry.register(
        ModelExecutionService(
            tenant=tenant,
            model=model,
            model_evaluator=evaluator,
        )
    )
    bootstrap_entities(manager, registry)
    return registry


@pytest.fixture
def problem_id(manager: Manager) -> str:
    return manager.name_cfg.problem_id


@pytest.fixture
def scenario_id(manager: Manager) -> str:
    return manager.name_cfg.scenario_id


@pytest.fixture
def proposal_id(manager: Manager) -> str:
    return manager.name_cfg.proposal_id


@pytest.fixture
def handler(
    manager: Manager,
    execution_manager_registry: ExecutionManagerRegistry,
    viewer: RecordingViewer,
    session_ownership_store: SessionOwnershipStore,
) -> Handler:
    return Handler(
        manager=manager,
        execution_manager_registry=execution_manager_registry,
        viewer=viewer,
        get_widgets_fn=viewer.get_widgets,
        get_widget_ids_by_groups_fn=viewer.get_widget_ids_by_groups,
        arrange_data_fn=_normalize_output,
        prepare_values_fn=lambda values: dict(values),
        session_ownership_store=session_ownership_store,
    )


@pytest.fixture
def client(handler: Handler, tenant: str) -> TestClient:
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=tenant,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def error_client(handler: Handler, tenant: str) -> TestClient:
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=tenant,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
