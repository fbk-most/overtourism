# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from overtourism.backend.api.v2.main import create_app
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType

from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


def _normalize_output(
    data: Any,
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


@dataclass
class RecordingDataLoader:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def get_categories(self, language: str = "it") -> dict[str, Any]:
        self.calls.append(("categories", {"language": language}))
        return {"language": language, "categories": ["pressure", "services"]}

    def get_list(self, category: str = "", language: str = "it") -> dict[str, Any]:
        self.calls.append(("list", {"category": category, "language": language}))
        return {"category": category, "language": language, "indexes": ["visits"]}

    def get_dataframe(self, dataframe: str) -> dict[str, Any]:
        self.calls.append(("dataframe", {"dataframe": dataframe}))
        return {"dataframe": dataframe, "rows": [{"value": 1}]}

    def get_map(self, map: str) -> dict[str, Any]:
        self.calls.append(("map", {"map": map}))
        return {"map": map, "features": [{"id": "feature-1"}]}


@pytest.fixture
def tenant() -> str:
    return "tenant-alpha"


@pytest.fixture
def viewer() -> RecordingViewer:
    return RecordingViewer()


@pytest.fixture
def data_loader() -> RecordingDataLoader:
    return RecordingDataLoader()


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
def problem_id(manager: Manager) -> str:
    return manager.base_problem_config.problem_id


@pytest.fixture
def scenario_id(manager: Manager) -> str:
    return manager.base_problem_config.scenario_id


@pytest.fixture
def proposal_id(manager: Manager) -> str:
    return manager.base_problem_config.proposal_id


@pytest.fixture
def handler(
    manager: Manager,
    viewer: RecordingViewer,
    data_loader: RecordingDataLoader,
) -> Handler:
    return Handler(
        manager=manager,
        viewer=viewer,
        data_loader=data_loader,
        arrange_data_fn=_normalize_output,
        prepare_values_fn=lambda values: dict(values),
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
