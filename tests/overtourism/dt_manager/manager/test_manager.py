# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

from overtourism.overtourism.bootstrap import bootstrap_default_graph
from overtourism.dt_manager.evaluation import evaluation as evaluation_module
from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.proposal import manager as proposal_manager_module
from overtourism.dt_manager.proposal import proposal as proposal_module
from overtourism.dt_manager.scenario import manager as scenario_manager_module
from overtourism.dt_manager.scenario import values as scenario_values_module
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.overtourism import registry as execution_registry_module
from overtourism.overtourism.registry import (
    ExecutionManagerRegistry,
    ModelExecutionService,
)
from tests.overtourism.dt_manager.conftest import FakeModelEvaluator

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
UPDATED_TIMESTAMP = "2026-05-15T09:00:00Z"


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


def test_manager_bootstraps_default_problem_when_store_is_empty(tmp_path) -> None:
    manager, evaluator, model, _ = _make_manager(tmp_path)
    default_config = BaseConfig()

    assert [problem.problem_id for problem in manager.list_problems()] == [
        default_config.problem_id
    ]

    problem = manager.read_problem(default_config.problem_id)
    assert problem.problem_id == default_config.problem_id
    assert problem.tenant == default_config.tenant
    assert problem.name == default_config.problem_name
    assert problem.description == default_config.problem_description

    assert [
        scenario.scenario_id
        for scenario in manager.list_scenarios(tenant=default_config.tenant)
    ] == [default_config.scenario_id]
    assert [
        proposal.proposal_id
        for proposal in manager.list_proposals(default_config.problem_id)
    ] == [default_config.proposal_id]
    assert manager.relationship_manager.get_related_scenario_ids(
        default_config.proposal_id,
    ) == [default_config.scenario_id]

    evaluation_manager = manager.evaluation_manager
    evaluations = evaluation_manager.list_evaluations(default_config.scenario_id)
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.state is EvaluationState.COMPLETED
    assert evaluation.scenario_id == default_config.scenario_id
    assert (
        evaluation.result.to_dict()
        if hasattr(evaluation.result, "to_dict")
        else evaluation.result
    ) == {"ensemble_size": 20, "values": {}}

    assert evaluator.evaluate_calls == [
        {"model": model, "ensemble_size": 20, "values": {}}
    ]
    assert manager.evaluation_manager.read_latest_evaluation(
        default_config.scenario_id
    ).result == {
        "ensemble_size": 20,
        "values": {},
    }


def test_manager_submanagers_persist_explicit_graph(tmp_path, monkeypatch) -> None:
    manager, evaluator, model, execution_manager = _make_manager(tmp_path)

    monkeypatch.setattr(proposal_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        proposal_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )
    monkeypatch.setattr(
        scenario_values_module, "get_timestamp", lambda: CREATED_TIMESTAMP
    )
    monkeypatch.setattr(
        scenario_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )
    monkeypatch.setattr(evaluation_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        execution_registry_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        tenant=manager.name_cfg.tenant,
        name="Problem Alpha",
        description="Primary problem",
        extras={"region": "tn"},
    )
    scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        tenant=problem.tenant,
        values={"visits": 7},
        name="Scenario Alpha",
        description="Primary scenario",
        extras={"kind": "scenario"},
    )
    proposal = manager.proposal_manager.create_proposal(
        "proposal-alpha",
        problem_id=problem.problem_id,
        name="Proposal Alpha",
        description="Primary proposal",
        status="draft",
        extras={"kind": "proposal"},
    )
    manager.relationship_manager.link_scenario_proposal(
        proposal_id=proposal.proposal_id,
        scenario_id=scenario.scenario_id,
    )

    evaluation = manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        scenario.scenario_id,
    )
    completed = execution_manager.execute_evaluation(
        evaluation,
        scenario,
        ensemble_size=4,
    )
    manager.evaluation_manager.save_evaluation(completed)

    assert problem.problem_id == "problem-alpha"
    assert scenario.scenario_id == "scenario-alpha"
    assert proposal.proposal_id == "proposal-alpha"
    assert completed.state is EvaluationState.COMPLETED
    assert completed.result.to_dict() == {
        "ensemble_size": 4,
        "values": {"visits": 7},
    }
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 4,
        "values": {"visits": 7},
    }

    assert {item.problem_id for item in manager.list_problems()} == {
        manager.name_cfg.problem_id,
        "problem-alpha",
    }
    assert {
        item.scenario_id for item in manager.list_scenarios(tenant=problem.tenant)
    } == {
        manager.name_cfg.scenario_id,
        scenario.scenario_id,
    }
    assert {
        item.proposal_id for item in manager.list_proposals(problem.problem_id)
    } == {
        proposal.proposal_id,
    }
    assert manager.relationship_manager.get_related_scenario_ids(
        proposal.proposal_id,
    ) == [scenario.scenario_id]
    assert manager.evaluation_manager.read_latest_evaluation(
        scenario.scenario_id
    ).result == {
        "ensemble_size": 4,
        "values": {"visits": 7},
    }


def test_manager_session_workflow_uses_session_manager(tmp_path) -> None:
    manager, evaluator, model, execution_manager = _make_manager(tmp_path)

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        tenant=manager.name_cfg.tenant,
        name="Problem Alpha",
        description="Primary problem",
    )
    base_scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        tenant=problem.tenant,
        values={"visits": 9},
        name="Draft Scenario",
        description="Transient scenario",
    )

    session = manager.create_session(metadata={"source": "test"})
    session_scenario = manager.create_session_scenario(
        session.session_id,
        base_scenario.scenario_id,
        values={"visits": 11},
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-session",
        scenario_id=session_scenario.scenario_id,
    )
    completed = execution_manager.execute_evaluation(
        running,
        session_scenario,
        ensemble_size=5,
    )
    session_evaluation = manager.create_session_evaluation(
        session.session_id,
        session_scenario.scenario_id,
        completed,
    )

    assert manager.read_session(session.session_id) is session
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
    assert session.active_scenario_id == session_scenario.scenario_id
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 11},
    }

    manager.delete_session(session.session_id)
    assert manager.list_sessions() == []


def test_manager_read_scenario_data_reuses_persisted_results(tmp_path) -> None:
    manager, evaluator, model, execution_manager = _make_manager(tmp_path)

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        tenant=manager.name_cfg.tenant,
        name="Problem Alpha",
        description="Primary problem",
    )
    scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        tenant=problem.tenant,
        values={"visits": 13},
        name="Scenario Alpha",
        description="Primary scenario",
    )

    evaluation = manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        scenario.scenario_id,
    )
    completed = execution_manager.execute_evaluation(
        evaluation,
        scenario,
        ensemble_size=3,
    )
    manager.evaluation_manager.save_evaluation(completed)

    assert (
        manager.evaluation_manager.read_latest_evaluation(scenario.scenario_id).result
        == completed.result.to_dict()
    )
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 3,
        "values": {"visits": 13},
    }
