# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from tests.overtourism.test_support import (
    DEFAULT_TENANT,
    FakeExecutionService,
    FakeModelEvaluator,
)


def _make_manager(
    tmp_path,
    *,
    evaluator: FakeModelEvaluator | None = None,
) -> tuple[Manager, FakeModelEvaluator, object, FakeExecutionService]:
    evaluator = FakeModelEvaluator() if evaluator is None else evaluator
    model = object()
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
    )
    manager.name_cfg = type("NameCfg", (), {"tenant": DEFAULT_TENANT})()
    execution_service = FakeExecutionService(model, evaluator)
    return manager, evaluator, model, execution_service


def test_session_manager_tracks_transient_session_workflow(tmp_path) -> None:
    manager, evaluator, model, execution_service = _make_manager(tmp_path)
    tenant = DEFAULT_TENANT

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        tenant=tenant,
        name="Problem Alpha",
        description="Primary problem",
    )
    session = manager.session_manager.create_session(metadata={"source": "test"})
    draft = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        tenant=problem.tenant,
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
    tenant = DEFAULT_TENANT

    manager.problem_manager.create_problem(
        "problem-alpha",
        tenant=tenant,
        name="Problem Alpha",
        description="Primary problem",
    )
    session = manager.session_manager.create_session()
    draft = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        tenant=tenant,
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
