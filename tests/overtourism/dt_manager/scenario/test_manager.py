# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.indexes.index import IndexEntry, IndexType
from overtourism.dt_manager.scenario import manager as scenario_manager_module
from overtourism.dt_manager.scenario import values as scenario_values_module
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.utils.exception import (
    ScenarioAlreadyExists,
    ScenarioDoesNotExist,
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
    problem_id = problem_payload["problem_id"]
    manager = ScenarioManager(problem_id, fake_model, fake_model_evaluator, sql_store)
    sql_store.save_problem(problem_id, problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    scenario = manager.create_scenario(
        "scenario-alpha",
        values={"visits": 7, "ignored": "skip"},
        name="Scenario Alpha",
        description="Primary scenario",
        extras={"kind": "scenario"},
    )

    assert scenario.problem_id == problem_id
    assert scenario.created == CREATED_TIMESTAMP
    assert scenario.updated == CREATED_TIMESTAMP
    assert scenario.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=7,
            index_type=IndexType.CONSTANT.value,
        )
    ]
    assert sql_store.load_scenario(problem_id, "scenario-alpha") == scenario.to_dict()
    assert manager.read_scenario("scenario-alpha").to_dict() == scenario.to_dict()

    with pytest.raises(ScenarioAlreadyExists):
        manager.create_scenario("scenario-alpha")

    manager.update_scenario("scenario-alpha", {"visits": 11})
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

    assert sql_store.load_scenario(problem_id, "scenario-alpha") == updated.to_dict()

    loaded = manager.list_scenarios()
    assert [item.scenario_id for item in loaded] == ["scenario-alpha"]
    assert loaded[0].index_values[0].to_dict() == {
        "index_name": "visits",
        "index_value": 11,
        "index_type": IndexType.CONSTANT.value,
    }
    assert loaded[0].to_dict() == updated.to_dict()

    manager.delete_scenario("scenario-alpha")
    assert sql_store.load_scenarios(problem_id) == []

    with pytest.raises(ScenarioDoesNotExist):
        manager.read_scenario("scenario-alpha")
    with pytest.raises(ScenarioDoesNotExist):
        sql_store.load_scenario(problem_id, "scenario-alpha")


def test_scenario_manager_exposes_only_stateless_scenario_operations(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = ScenarioManager(problem_id, fake_model, fake_model_evaluator, sql_store)

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
    problem_id = problem_payload["problem_id"]
    manager = ScenarioManager(problem_id, fake_model, fake_model_evaluator, sql_store)
    sql_store.save_problem(problem_id, problem_payload)

    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    base_scenario = manager.create_scenario(
        "scenario-alpha",
        values={"visits": 5},
        name="Scenario Alpha",
        description="Primary scenario",
    )

    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: SESSION_TIMESTAMP
    )
    session_scenario = manager.build_session_scenario(
        "session-1",
        "scenario-alpha",
        {"visits": 9},
    )

    assert session_scenario.problem_id == problem_id
    assert session_scenario.scenario_id.startswith("scenario-alpha_session-1_")
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
    updated_session_scenario = manager.update_scenario_object(
        session_scenario,
        values={"visits": 12},
    )
    assert updated_session_scenario.scenario_id == session_scenario.scenario_id
    assert updated_session_scenario.updated == UPDATED_TIMESTAMP
    assert updated_session_scenario.version == session_scenario.version + 1
    assert updated_session_scenario.index_values == [
        IndexEntry(
            index_name="visits",
            index_value=12,
            index_type=IndexType.CONSTANT.value,
        )
    ]

    saved_session_scenario = manager.save_scenario_object(updated_session_scenario)
    assert saved_session_scenario.to_dict() == updated_session_scenario.to_dict()
    assert manager.read_scenario(session_scenario.scenario_id).to_dict() == (
        updated_session_scenario.to_dict()
    )
