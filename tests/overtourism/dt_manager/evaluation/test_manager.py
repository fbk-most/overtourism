# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.classes.indexes import IndexEntry, IndexType
from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    EvaluationState,
)
from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.utils.exception import EvaluationDoesNotExist

from overtourism.dt_manager.evaluation import evaluation as evaluation_module
from overtourism.dt_manager.evaluation import manager as evaluation_manager_module

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
FINISHED_TIMESTAMP = "2026-05-15T09:00:00Z"
SESSION_TIMESTAMP = "2026-05-15T10:00:00Z"


def _make_scenario(problem_id: str, scenario_id: str, visits: int) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        problem_id=problem_id,
        name=f"{scenario_id} name",
        description=f"{scenario_id} description",
        created="2026-05-15T07:00:00Z",
        updated="2026-05-15T07:00:00Z",
        extras={"kind": "scenario"},
        index_values=[
            IndexEntry(
                index_name="visits",
                index_value=visits,
                index_type=IndexType.CONSTANT.value,
            )
        ],
    )


def _make_manager(
    sql_store, fake_model, fake_model_evaluator, problem_id: str
) -> EvaluationManager:
    return EvaluationManager(
        sql_store,
        problem_id,
        Executor(fake_model, fake_model_evaluator),
    )


def _persist_problem_scenarios(sql_store, problem_payload: dict, *scenarios: Scenario) -> None:
    problem_id = problem_payload["problem_id"]
    sql_store.save_problem(problem_id, problem_payload)
    for scenario in scenarios:
        sql_store.save_scenario(problem_id, scenario.scenario_id, scenario.to_dict())


def test_create_run_load_and_delete_evaluation(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    monkeypatch.setattr(evaluation_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        evaluation_manager_module, "get_timestamp", lambda: FINISHED_TIMESTAMP
    )

    scenario = _make_scenario(problem_id, "scenario-alpha", 7)
    _persist_problem_scenarios(sql_store, problem_payload, scenario)

    running = manager.create_evaluation("evaluation-alpha", scenario.scenario_id)
    assert running.state is EvaluationState.RUNNING
    assert running.started == CREATED_TIMESTAMP
    assert (
        sql_store.load_evaluation(problem_id, "evaluation-alpha")["state"]
        == EvaluationState.RUNNING.value
    )

    completed = manager.run_evaluation(
        "evaluation-alpha",
        scenario,
        ensemble_size=4,
        model_tag="baseline",
    )

    assert completed.state is EvaluationState.COMPLETED
    assert completed.finished == FINISHED_TIMESTAMP
    assert completed.result.to_dict() == {
        "ensemble_size": 4,
        "values": {"visits": 7},
    }
    assert fake_model_evaluator.evaluate_calls[-1] == {
        "model": fake_model,
        "ensemble_size": 4,
        "values": {"visits": 7},
        "model_tag": "baseline",
    }
    latest = manager.read_latest_evaluation(scenario.scenario_id)
    assert latest.to_dict() == completed.to_dict()

    latest.state = EvaluationState.FAILED
    assert manager.read_evaluation("evaluation-alpha").state is EvaluationState.COMPLETED

    reloaded_manager = _make_manager(
        sql_store, fake_model, fake_model_evaluator, problem_id
    )
    loaded = reloaded_manager.list_evaluations()

    assert [item.evaluation_id for item in loaded] == ["evaluation-alpha"]
    assert loaded[0].result.to_dict() == completed.result.to_dict()
    assert (
        reloaded_manager.read_evaluation("evaluation-alpha").state
        is EvaluationState.COMPLETED
    )

    manager.delete_evaluation("evaluation-alpha")
    assert sql_store.load_evaluations(problem_id) == []

    with pytest.raises(EvaluationDoesNotExist):
        manager.read_evaluation("evaluation-alpha")


def test_session_evaluation_lifecycle_and_save_session(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    monkeypatch.setattr(evaluation_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        evaluation_manager_module, "get_timestamp", lambda: SESSION_TIMESTAMP
    )

    scenario = _make_scenario(problem_id, "scenario-alpha", 11)
    _persist_problem_scenarios(sql_store, problem_payload, scenario)

    session_evaluation = manager.create_session_evaluation(
        "session-1",
        "evaluation-session",
        scenario.scenario_id,
        type=DEFAULT_EVALUATION_TYPE,
    )
    assert session_evaluation.state is EvaluationState.RUNNING
    assert session_evaluation.started == CREATED_TIMESTAMP
    assert manager.read_session_evaluation("session-1") is session_evaluation

    completed = manager.run_session_evaluation("session-1", scenario, ensemble_size=3)
    assert completed.state is EvaluationState.COMPLETED
    assert completed.result.to_dict() == {
        "ensemble_size": 3,
        "values": {"visits": 11},
    }

    saved = manager.save_session_evaluation("session-1")
    assert saved is completed
    assert manager.read_evaluation(saved.evaluation_id).to_dict() == saved.to_dict()
    assert (
        sql_store.load_evaluation(problem_id, saved.evaluation_id)["state"]
        == EvaluationState.COMPLETED.value
    )

    manager.close_session("session-1")
    with pytest.raises(EvaluationDoesNotExist):
        manager.read_session_evaluation("session-1")

    reloaded_manager = _make_manager(
        sql_store, fake_model, fake_model_evaluator, problem_id
    )
    loaded = reloaded_manager.read_evaluation(saved.evaluation_id)

    assert loaded.result.to_dict() == completed.result.to_dict()
    assert reloaded_manager.read_evaluation(saved.evaluation_id).to_dict() == loaded.to_dict()


def test_delete_evaluations_for_scenario_clears_persistent_and_session_state(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    monkeypatch.setattr(evaluation_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        evaluation_manager_module, "get_timestamp", lambda: FINISHED_TIMESTAMP
    )

    primary_scenario = _make_scenario(problem_id, "scenario-alpha", 5)
    secondary_scenario = _make_scenario(problem_id, "scenario-beta", 9)
    _persist_problem_scenarios(
        sql_store,
        problem_payload,
        primary_scenario,
        secondary_scenario,
    )

    manager.create_evaluation("evaluation-alpha", primary_scenario.scenario_id)
    manager.run_evaluation("evaluation-alpha", primary_scenario, ensemble_size=2)

    manager.create_session_evaluation(
        "session-1",
        "evaluation-session",
        primary_scenario.scenario_id,
    )
    manager.run_session_evaluation("session-1", primary_scenario, ensemble_size=2)

    manager.create_evaluation("evaluation-beta", secondary_scenario.scenario_id)
    manager.run_evaluation("evaluation-beta", secondary_scenario, ensemble_size=2)

    manager.delete_evaluations_for_scenario(primary_scenario.scenario_id)

    assert [item.evaluation_id for item in manager.list_evaluations()] == [
        "evaluation-beta"
    ]
    assert (
        sql_store.load_evaluations(problem_id)[0]["evaluation_id"]
        == "evaluation-beta"
    )

    with pytest.raises(EvaluationDoesNotExist):
        manager.read_session_evaluation("session-1")
    with pytest.raises(EvaluationDoesNotExist):
        manager.read_evaluation("evaluation-alpha")
