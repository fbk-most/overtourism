# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

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


def _normalize_output(data: Any) -> dict[str, Any]:
    if hasattr(data, "to_dict"):
        return data.to_dict()
    if hasattr(data, "to_snapshot"):
        return data.to_snapshot()
    return data


def test_get_saved_scenario_data_falls_back_to_stored_scenario_when_session_has_other_draft(
    tmp_path,
) -> None:
    tenant = "tenant-alpha"
    model = SimpleNamespace(name="fake-model", indexes=[])
    evaluator = FakeModelEvaluator(model)
    manager = Manager(
        model=model,
        model_evaluator=evaluator,
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        base_problem_config=BaseConfig(tenant=tenant),
    )
    handler = Handler(
        manager=manager,
        arrange_data_fn=_normalize_output,
        prepare_values_fn=lambda values: dict(values),
    )
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=tenant,
        subject=None,
        token=None,
        claims={},
    )

    problem_id = manager.base_problem_config.problem_id
    base_scenario_id = manager.base_problem_config.scenario_id
    session_id = "session-1"

    first_draft = manager.session_manager.evaluate_session(
        problem_id,
        session_id,
        base_scenario_id,
        values={"visits": 5},
        ensemble_size=4,
    )
    second_draft = manager.session_manager.evaluate_session(
        problem_id,
        session_id,
        base_scenario_id,
        values={"visits": 11},
        ensemble_size=4,
    )
    saved = manager.session_manager.save_session_scenario(
        problem_id,
        session_id,
        scenario_id=second_draft.scenario_id,
        name="Saved Draft",
    )

    assert manager.session_manager.read_session(problem_id, session_id).active_scenario_id == (
        first_draft.scenario_id
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/scenarios/{saved.scenario_id}",
            params={"problem_id": problem_id, "session_id": session_id},
        )

    assert response.status_code == 200
    assert response.json()["scenario_id"] == saved.scenario_id
    assert response.json()["data"] == {
        "ensemble_size": 4,
        "values": {"visits": 11},
    }