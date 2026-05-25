# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.classes.indexes import IndexEntry, IndexType
from overtourism.dt_manager.evaluation import evaluation as evaluation_module
from overtourism.dt_manager.evaluation import manager as evaluation_manager_module
from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    EvaluationState,
)
from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.utils.exception import (
    EvaluationAlreadyExists,
    EvaluationDoesNotExist,
)

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


def _persist_problem_scenarios(
    sql_store, problem_payload: dict, *scenarios: Scenario
) -> None:
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
    }
    latest = manager.read_latest_evaluation(scenario.scenario_id)
    assert latest.to_dict() == completed.to_dict()

    latest.state = EvaluationState.FAILED
    assert (
        manager.read_evaluation("evaluation-alpha").state is EvaluationState.COMPLETED
    )

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


def test_evaluation_manager_exposes_only_persistent_and_object_lifecycle_operations(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    assert not hasattr(manager, "create_session_evaluation")
    assert not hasattr(manager, "read_session_evaluation")
    assert not hasattr(manager, "save_session_evaluation")
    assert not hasattr(manager, "delete_session_evaluation")
    assert not hasattr(manager, "run_session_evaluation")
    assert not hasattr(manager, "rerun_session_evaluation")
    assert not hasattr(manager, "close_session")


def test_evaluation_objects_can_be_executed_saved_and_rerun(
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

    evaluation = manager.build_running_evaluation(
        "evaluation-session",
        scenario_id=scenario.scenario_id,
        type=DEFAULT_EVALUATION_TYPE,
    )
    assert evaluation.state is EvaluationState.RUNNING
    assert evaluation.started == CREATED_TIMESTAMP

    completed = manager.execute_evaluation(evaluation, scenario, ensemble_size=3)
    assert completed.state is EvaluationState.COMPLETED
    assert completed.finished == SESSION_TIMESTAMP
    assert completed.result.to_dict() == {
        "ensemble_size": 3,
        "values": {"visits": 11},
    }
    assert fake_model_evaluator.evaluate_calls[-1] == {
        "model": fake_model,
        "ensemble_size": 3,
        "values": {"visits": 11},
    }

    manager.save_evaluation(completed)
    assert manager.read_evaluation(completed.evaluation_id).to_dict() == (
        completed.to_dict()
    )
    assert (
        sql_store.load_evaluation(problem_id, completed.evaluation_id)["state"]
        == EvaluationState.COMPLETED.value
    )

    monkeypatch.setattr(
        evaluation_manager_module, "get_timestamp", lambda: FINISHED_TIMESTAMP
    )
    rerun = manager.rerun_evaluation_object(
        completed,
        scenario,
        ensemble_size=6,
        persist=True,
    )

    assert rerun.evaluation_id == completed.evaluation_id
    assert rerun.version == completed.version + 1
    assert rerun.finished == FINISHED_TIMESTAMP
    assert rerun.result.to_dict() == {
        "ensemble_size": 6,
        "values": {"visits": 11},
    }
    assert fake_model_evaluator.evaluate_calls[-1] == {
        "model": fake_model,
        "ensemble_size": 6,
        "values": {"visits": 11},
    }
    assert manager.read_evaluation(rerun.evaluation_id).to_dict() == rerun.to_dict()

    reloaded_manager = _make_manager(
        sql_store, fake_model, fake_model_evaluator, problem_id
    )
    loaded = reloaded_manager.read_evaluation(rerun.evaluation_id)

    assert loaded.result.to_dict() == rerun.result.to_dict()
    assert reloaded_manager.read_evaluation(rerun.evaluation_id).to_dict() == (
        loaded.to_dict()
    )


def test_delete_evaluations_for_scenario_clears_matching_persistent_state(
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

    manager.create_evaluation("evaluation-beta", secondary_scenario.scenario_id)
    manager.run_evaluation("evaluation-beta", secondary_scenario, ensemble_size=2)

    manager.delete_evaluations_for_scenario(primary_scenario.scenario_id)

    assert [item.evaluation_id for item in manager.list_evaluations()] == [
        "evaluation-beta"
    ]
    assert (
        sql_store.load_evaluations(problem_id)[0]["evaluation_id"] == "evaluation-beta"
    )

    with pytest.raises(EvaluationDoesNotExist):
        manager.read_evaluation("evaluation-alpha")


def test_duplicate_and_missing_evaluation_operations_raise_clear_errors(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    scenario = _make_scenario(problem_id, "scenario-alpha", 9)
    _persist_problem_scenarios(sql_store, problem_payload, scenario)

    manager.create_evaluation("evaluation-alpha", scenario.scenario_id)

    with pytest.raises(EvaluationAlreadyExists):
        manager.create_evaluation("evaluation-alpha", scenario.scenario_id)

    with pytest.raises(EvaluationDoesNotExist, match="scenario scenario-missing"):
        manager.read_latest_evaluation("scenario-missing")


def test_failed_evaluations_are_marked_failed_and_cannot_be_finished_twice(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    monkeypatch.setattr(
        evaluation_manager_module,
        "get_timestamp",
        lambda: FINISHED_TIMESTAMP,
    )

    scenario = _make_scenario(problem_id, "scenario-alpha", 13)
    _persist_problem_scenarios(sql_store, problem_payload, scenario)
    manager.create_evaluation("evaluation-failure", scenario.scenario_id)

    def _boom(*args, **kwargs):
        raise RuntimeError("evaluation failed")

    monkeypatch.setattr(manager.executor, "execute", _boom)

    with pytest.raises(RuntimeError, match="evaluation failed"):
        manager.run_evaluation("evaluation-failure", scenario, ensemble_size=3)

    failed = manager.read_evaluation("evaluation-failure")
    assert failed.state is EvaluationState.FAILED
    assert failed.finished == FINISHED_TIMESTAMP
    assert failed.version == 2

    with pytest.raises(ValueError, match="must be RUNNING"):
        manager.execute_evaluation(failed, scenario)


def test_delete_evaluations_for_scenario_ignores_missing_persisted_rows(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    scenario = _make_scenario(problem_id, "scenario-alpha", 5)
    _persist_problem_scenarios(sql_store, problem_payload, scenario)

    manager.create_evaluation("evaluation-alpha", scenario.scenario_id)
    manager.run_evaluation("evaluation-alpha", scenario, ensemble_size=2)

    original_delete = manager.store.delete_evaluation

    def _delete_once(problem_id_arg: str, evaluation_id: str) -> None:
        if evaluation_id == "evaluation-alpha":
            original_delete(problem_id_arg, evaluation_id)
            raise EvaluationDoesNotExist(
                f"Evaluation with ID {evaluation_id} does not exist"
            )
        original_delete(problem_id_arg, evaluation_id)

    monkeypatch.setattr(manager.store, "delete_evaluation", _delete_once)

    manager.delete_evaluations_for_scenario(scenario.scenario_id)

    assert manager.list_evaluations(scenario.scenario_id) == []


def test_build_evaluation_preserves_none_results_without_rebuilding_them(
    sql_store,
    fake_model,
    fake_model_evaluator,
    problem_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = _make_manager(sql_store, fake_model, fake_model_evaluator, problem_id)

    sql_store.save_problem(problem_id, problem_payload)
    sql_store.save_scenario(
        problem_id,
        "scenario-alpha",
        _make_scenario(problem_id, "scenario-alpha", 2).to_dict(),
    )
    sql_store.save_evaluation(
        problem_id,
        "evaluation-plain",
        {
            "evaluation_id": "evaluation-plain",
            "scenario_id": "scenario-alpha",
            "type": DEFAULT_EVALUATION_TYPE,
            "version": 1,
            "state": EvaluationState.COMPLETED.value,
            "started": CREATED_TIMESTAMP,
            "finished": FINISHED_TIMESTAMP,
            "result": None,
        },
    )

    loaded = manager.read_evaluation("evaluation-plain")

    assert loaded.result is None
