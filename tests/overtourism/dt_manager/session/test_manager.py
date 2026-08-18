# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest

from overtourism.overtourism.bootstrap import bootstrap_default_graph
from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.overtourism.registry import (
    ExecutionManagerRegistry,
    ModelExecutionService,
)
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


def _make_manager(
    tmp_path,
    *,
    evaluator: FakeModelEvaluator | None = None,
    names_cfg: BaseConfig | None = None,
) -> tuple[Manager, FakeModelEvaluator, SimpleNamespace, ModelExecutionService]:
    evaluator = FakeModelEvaluator() if evaluator is None else evaluator
    model = SimpleNamespace(name="fake-model")
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        names_cfg=names_cfg,
    )
    execution_registry = ExecutionManagerRegistry()
    execution_manager = ModelExecutionService(
        tenant=manager.name_cfg.tenant,
        model=model,
        model_evaluator=evaluator,
    )
    execution_registry.register(execution_manager)
    bootstrap_default_graph(manager, execution_registry)
    return manager, evaluator, model, execution_manager


def test_session_manager_tracks_transient_session_workflow(tmp_path) -> None:
    manager, evaluator, model, execution_manager = _make_manager(tmp_path)
    tenant = manager.name_cfg.tenant

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
        values={"visits": 8},
        name="Draft Scenario",
        description="Transient scenario",
    )

    session_scenario = manager.session_manager.create_session_scenario(
        session.session_id,
        draft,
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-alpha",
        scenario_id=session_scenario.scenario_id,
    )
    completed = execution_manager.execute_evaluation(
        running,
        session_scenario,
        ensemble_size=5,
    )
    session_evaluation = manager.session_manager.create_session_evaluation(
        session.session_id,
        session_scenario.scenario_id,
        completed,
    )

    assert session.metadata == {"source": "test"}
    assert session.active_scenario_id == session_scenario.scenario_id
    assert manager.session_manager.read_session(session.session_id) is session
    assert (
        manager.session_manager.read_session_scenario(
            session.session_id,
            session_scenario.scenario_id,
        )
        is session_scenario
    )
    assert (
        manager.session_manager.read_session_evaluation(
            session.session_id,
            session_scenario.scenario_id,
        )
        is session_evaluation
    )
    assert session_evaluation.state is EvaluationState.COMPLETED
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 8},
    }


def test_session_manager_can_remove_session_drafts_and_sessions(tmp_path) -> None:
    manager, _evaluator, _model, execution_manager = _make_manager(tmp_path)
    tenant = manager.name_cfg.tenant

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
        values={"visits": 11},
        name="Draft Scenario",
        description="Transient scenario",
    )
    session_scenario = manager.session_manager.create_session_scenario(
        session.session_id,
        draft,
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-alpha",
        scenario_id=session_scenario.scenario_id,
    )
    completed = execution_manager.execute_evaluation(
        running,
        session_scenario,
        ensemble_size=4,
    )
    manager.session_manager.create_session_evaluation(
        session.session_id,
        session_scenario.scenario_id,
        completed,
    )

    manager.session_manager.delete_session_scenario(
        session.session_id,
        session_scenario.scenario_id,
    )

    assert manager.session_manager.read_session(session.session_id).scenarios == {}
    assert manager.session_manager.read_session(session.session_id).evaluations == {}
    assert (
        manager.session_manager.read_session(session.session_id).active_scenario_id
        is None
    )

    with pytest.raises(KeyError):
        manager.session_manager.read_session_scenario(
            session.session_id,
            session_scenario.scenario_id,
        )
    with pytest.raises(KeyError):
        manager.session_manager.read_session_evaluation(
            session.session_id,
            session_scenario.scenario_id,
        )

    manager.session_manager.delete_session(session.session_id)
    assert manager.session_manager.list_sessions() == []
    with pytest.raises(KeyError):
        manager.session_manager.read_session(session.session_id)
