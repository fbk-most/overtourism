# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.session.config import SessionCleanupConfig
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from tests.overtourism.test_support import (
    DEFAULT_TERRITORY,
    FakeExecutionService,
    FakeModelEvaluator,
)


def _make_manager(
    tmp_path,
    *,
    evaluator: FakeModelEvaluator | None = None,
    session_cleanup_config: SessionCleanupConfig | None = None,
) -> tuple[Manager, FakeModelEvaluator, object, FakeExecutionService]:
    evaluator = FakeModelEvaluator() if evaluator is None else evaluator
    model = object()
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        session_cleanup_config=session_cleanup_config,
    )
    manager.name_cfg = type("NameCfg", (), {"territory": DEFAULT_TERRITORY})()
    execution_service = FakeExecutionService(model, evaluator)
    return manager, evaluator, model, execution_service


def test_session_manager_tracks_transient_session_workflow(tmp_path) -> None:
    manager, evaluator, model, execution_service = _make_manager(tmp_path)
    territory = DEFAULT_TERRITORY

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        territory=territory,
        name="Problem Alpha",
        description="Primary problem",
    )
    session = manager.session_manager.create_session(metadata={"source": "test"})
    draft = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        territory=problem.territory,
        param_overrides={"visits": 8},
        name="Draft Scenario",
        description="Transient scenario",
    )

    session_scenario = manager.create_session_scenario(
        session.session_id,
        draft.scenario_id,
        param_overrides=draft.param_overrides,
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-alpha",
        scenario_id=session_scenario.scenario_id,
    )
    completed = execution_service.execute_evaluation(
        running,
        session_scenario,
        ensemble_size=5,
    )
    session_evaluation = manager.create_session_evaluation(
        session.session_id,
        session_scenario.scenario_id,
        completed,
    )

    assert session.metadata == {"source": "test"}
    assert (
        manager.session_manager.read_session(session.session_id).active_scenario_id
        == session_scenario.scenario_id
    )
    reloaded_session = manager.session_manager.read_session(session.session_id)
    assert reloaded_session.metadata == session.metadata
    expected_draft = {
        key: value
        for key, value in session_scenario.to_dict().items()
        if not key.startswith("_")
    }
    assert (
        manager.read_session_scenario(
            session.session_id,
            session_scenario.scenario_id,
        ).to_dict()
        == expected_draft
    )
    assert (
        manager.read_session_evaluation(
            session.session_id,
            session_scenario.scenario_id,
        ).to_dict()
        == session_evaluation.to_dict()
    )
    assert session_evaluation.state is EvaluationState.COMPLETED
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 8},
    }


def test_session_manager_can_remove_session_drafts_and_sessions(tmp_path) -> None:
    manager, _evaluator, _model, execution_service = _make_manager(tmp_path)
    territory = DEFAULT_TERRITORY

    manager.problem_manager.create_problem(
        "problem-alpha",
        territory=territory,
        name="Problem Alpha",
        description="Primary problem",
    )
    session = manager.session_manager.create_session()
    draft = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        territory=territory,
        param_overrides={"visits": 11},
        name="Draft Scenario",
        description="Transient scenario",
    )
    session_scenario = manager.create_session_scenario(
        session.session_id,
        draft.scenario_id,
        param_overrides=draft.param_overrides,
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-alpha",
        scenario_id=session_scenario.scenario_id,
    )
    completed = execution_service.execute_evaluation(
        running,
        session_scenario,
        ensemble_size=4,
    )
    manager.create_session_evaluation(
        session.session_id,
        session_scenario.scenario_id,
        completed,
    )

    manager.delete_session_scenario(
        session.session_id,
        session_scenario.scenario_id,
    )

    assert manager.read_session(session.session_id).scenarios == {}
    assert manager.read_session(session.session_id).evaluations == {}
    assert manager.read_session(session.session_id).active_scenario_id is None

    with pytest.raises(EntityDoesNotExist):
        manager.read_session_scenario(
            session.session_id,
            session_scenario.scenario_id,
        )
    with pytest.raises(EntityDoesNotExist):
        manager.read_session_evaluation(
            session.session_id,
            session_scenario.scenario_id,
        )

    manager.delete_session(session.session_id)
    assert manager.list_sessions() == []
    with pytest.raises(EntityDoesNotExist):
        manager.read_session(session.session_id)


def test_expired_session_is_unavailable_before_periodic_cleanup(tmp_path) -> None:
    manager = _make_manager(tmp_path)[0]
    session = manager.session_manager.create_session()
    session_data = manager.store.load_session(session.session_id)
    session_data["created"] = "2000-01-01T00:00:00Z"
    manager.store.save_session(session_data)

    with pytest.raises(EntityDoesNotExist):
        manager.read_session(session.session_id)
    with pytest.raises(EntityDoesNotExist):
        manager.list_session_scenarios(session.session_id)
    with pytest.raises(EntityDoesNotExist):
        manager.list_session_evaluations(session.session_id)

    assert manager.list_sessions() == []


def test_session_cleanup_uses_configured_ttl(tmp_path) -> None:
    cleanup_config = SessionCleanupConfig(
        session_scenario_ttl_seconds=10,
        session_cleanup_interval_seconds=86400,
    )
    manager = _make_manager(
        tmp_path,
        session_cleanup_config=cleanup_config,
    )[0]
    now = datetime.now(timezone.utc)
    expired = manager.session_manager.create_session()
    active = manager.session_manager.create_session()
    expired_data = manager.store.load_session(expired.session_id)
    active_data = manager.store.load_session(active.session_id)
    expired_data["created"] = (now - timedelta(seconds=11)).isoformat()
    active_data["created"] = (now - timedelta(seconds=9)).isoformat()
    manager.store.save_session(expired_data)
    manager.store.save_session(active_data)

    deleted_count = manager.session_manager.delete_expired_sessions(now=now)

    assert deleted_count == 1
    assert [session.session_id for session in manager.list_sessions()] == [
        active.session_id,
    ]
    with pytest.raises(EntityDoesNotExist):
        manager.read_session(expired.session_id)


def test_session_cleanup_config_defaults_to_weekly_ttl_and_daily_interval() -> None:
    config = SessionCleanupConfig()

    assert config.session_scenario_ttl_seconds == 604800
    assert config.session_cleanup_interval_seconds == 86400


@pytest.mark.parametrize(
    "config_values",
    [
        {"session_scenario_ttl_seconds": 0},
        {"session_cleanup_interval_seconds": -1},
        {"session_scenario_ttl_seconds": float("nan")},
        {"session_cleanup_interval_seconds": float("inf")},
    ],
)
def test_session_cleanup_config_rejects_invalid_durations(config_values) -> None:
    with pytest.raises(ValueError):
        SessionCleanupConfig(**config_values)
