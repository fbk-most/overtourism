# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.indexes.index import IndexEntry, IndexType
from overtourism.dt_manager.scenario import manager as scenario_manager_module
from overtourism.dt_manager.scenario import values as scenario_values_module
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    ScenarioAlreadyExists,
)

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
UPDATED_TIMESTAMP = "2026-05-15T09:00:00Z"
SESSION_TIMESTAMP = "2026-05-15T10:00:00Z"


def test_create_update_save_load_and_delete_scenario(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    tenant = problem_payload["tenant"]
    manager = ScenarioManager(
        f"{tenant}_base_scenario",
        sql_store,
    )
    sql_store.save_problem(problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    scenario = manager.create_scenario(
        "scenario-alpha",
        tenant,
        param_overrides={"visits": 7, "ignored": "skip"},
        name="Scenario Alpha",
        description="Primary scenario",
        extras={"kind": "scenario"},
    )

    assert scenario.tenant == tenant
    assert scenario.created == CREATED_TIMESTAMP
    assert scenario.updated == CREATED_TIMESTAMP
    assert scenario.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=7,
            index_type=IndexType.CONSTANT.value,
        )
    ]
    persisted = sql_store.load_scenario("scenario-alpha")
    assert persisted == scenario.to_dict()
    assert manager.read_scenario("scenario-alpha").to_dict() == scenario.to_dict()

    with pytest.raises(ScenarioAlreadyExists):
        manager.create_scenario("scenario-alpha", tenant)

    manager.update_scenario("scenario-alpha", param_overrides={"visits": 11})
    updated = manager.read_scenario("scenario-alpha")

    assert updated.updated == UPDATED_TIMESTAMP
    assert updated.name == "Scenario Alpha"
    assert updated.description == "Primary scenario"
    assert updated.extras == {"kind": "scenario"}
    assert updated.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=11,
            index_type=IndexType.CONSTANT.value,
        )
    ]

    assert sql_store.load_scenario("scenario-alpha") == updated.to_dict()

    loaded = manager.list_scenarios(tenant=tenant)
    assert [item.scenario_id for item in loaded] == ["scenario-alpha"]
    assert loaded[0].index_values[0].to_dict() == {
        "index_name": "visits",
        "index_value": 11,
        "index_type": IndexType.CONSTANT.value,
    }
    assert loaded[0].to_dict() == updated.to_dict()

    manager.delete_scenario("scenario-alpha")
    assert sql_store.load_scenarios() == []

    with pytest.raises(EntityDoesNotExist):
        manager.read_scenario("scenario-alpha")
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_scenario("scenario-alpha")


def test_update_scenario_preserves_existing_values_when_overriding_subset(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    tenant = problem_payload["tenant"]
    manager = ScenarioManager(
        f"{tenant}_base_scenario",
        sql_store,
    )
    sql_store.save_problem(problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    manager.create_scenario(
        "scenario-alpha",
        tenant,
        param_overrides={"tourists_parking_percentage": 0.02, "tourists_per_vehicle": 2.5},
    )

    manager.update_scenario(
        "scenario-alpha",
        param_overrides={"tourists_parking_percentage": 0.61},
    )
    updated = manager.read_scenario("scenario-alpha")

    assert updated.updated == UPDATED_TIMESTAMP
    assert {item.index_name: item.index_value for item in updated.index_values} == {
        "tourists_parking_percentage": 0.61,
        "tourists_per_vehicle": 2.5,
    }


def test_scenario_manager_exposes_only_stateless_scenario_operations(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
) -> None:
    tenant = problem_payload["tenant"]
    manager = ScenarioManager(
        f"{tenant}_base_scenario",
        sql_store,
    )

    assert not hasattr(manager, "create_session_scenario")
    assert not hasattr(manager, "update_session_scenario")
    assert not hasattr(manager, "save_session_scenario")
    assert not hasattr(manager, "register_session_scenario")
    assert not hasattr(manager, "read_session_scenario")
    assert not hasattr(manager, "has_session")
    assert not hasattr(manager, "close_session")


def test_scenario_manager_builds_updates_and_saves_transient_scenario_objects(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    tenant = problem_payload["tenant"]
    manager = ScenarioManager(
        f"{tenant}_base_scenario",
        sql_store,
    )
    sql_store.save_problem(problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    base_scenario = manager.create_scenario(
        "scenario-alpha",
        tenant,
        param_overrides={"visits": 5},
        name="Scenario Alpha",
        description="Primary scenario",
    )

    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: SESSION_TIMESTAMP
    )
    session_scenario = manager.detach_scenario(
        "scenario-alpha",
        {"visits": 9},
    )

    assert session_scenario.tenant == tenant
    assert session_scenario.scenario_id != base_scenario.scenario_id
    assert session_scenario.name == base_scenario.name
    assert session_scenario.description == base_scenario.description
    assert session_scenario.created == SESSION_TIMESTAMP
    assert session_scenario.updated == SESSION_TIMESTAMP
    assert session_scenario.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=9,
            index_type=IndexType.CONSTANT.value,
        )
    ]

    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )
    updated_session_scenario = manager.update_detached_scenario(
        session_scenario,
        param_overrides={"visits": 12},
    )
    assert updated_session_scenario.scenario_id == session_scenario.scenario_id
    assert updated_session_scenario.updated == UPDATED_TIMESTAMP
    assert updated_session_scenario.version == session_scenario.version
    assert updated_session_scenario.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=12,
            index_type=IndexType.CONSTANT.value,
        )
    ]


def test_detach_scenario_preserves_existing_values_when_overriding_subset(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    tenant = problem_payload["tenant"]
    manager = ScenarioManager(
        f"{tenant}_base_scenario",
        sql_store,
    )
    sql_store.save_problem(problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    manager.create_scenario(
        "scenario-alpha",
        tenant,
        param_overrides={"tourists_parking_percentage": 0.02, "tourists_per_vehicle": 2.5},
    )

    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: SESSION_TIMESTAMP
    )
    draft = manager.detach_scenario(
        "scenario-alpha",
        values={"tourists_parking_percentage": 0.61},
    )

    assert draft.created == SESSION_TIMESTAMP
    assert draft.updated == SESSION_TIMESTAMP
    assert {item.index_name: item.index_value for item in draft.index_values} == {
        "tourists_parking_percentage": 0.61,
        "tourists_per_vehicle": 2.5,
    }
