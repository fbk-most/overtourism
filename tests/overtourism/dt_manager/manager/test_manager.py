# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest

from overtourism.dt_manager.evaluation.evaluation import Evaluation, EvaluationState
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.session import manager as session_manager_module
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.dt_manager.utils.metadata import ExtrasConfig
from tests.overtourism.test_support import (
    DEFAULT_TERRITORY,
    FakeExecutionService,
    FakeModelEvaluator,
)

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
UPDATED_TIMESTAMP = "2026-05-15T09:00:00Z"


def _make_manager(
    tmp_path,
    *,
    evaluator: FakeModelEvaluator | None = None,
) -> tuple[Manager, FakeModelEvaluator, SimpleNamespace, FakeExecutionService]:
    evaluator = FakeModelEvaluator() if evaluator is None else evaluator
    model = SimpleNamespace(name="fake-model")
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        extras_config=ExtrasConfig(
            problem_keys=frozenset({"objective", "links"}),
        ),
    )
    execution_service = FakeExecutionService(model, evaluator)
    return manager, evaluator, model, execution_service


def test_create_session_requires_territory(tmp_path) -> None:
    manager = _make_manager(tmp_path)[0]

    with pytest.raises(TypeError):
        getattr(manager, "create_session")()


def test_manager_starts_empty_and_persists_an_explicit_graph(tmp_path) -> None:
    manager, evaluator, model, execution_service = _make_manager(tmp_path)

    assert manager.list_problems() == []
    assert manager.list_scenarios() == []
    assert manager.list_proposals() == []
    assert manager.list_sessions() == []
    assert manager.list_evaluations() == []

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        territory=DEFAULT_TERRITORY,
        name="Problem Alpha",
        description="Primary problem",
        extras={"region": "tn"},
    )
    scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        DEFAULT_TERRITORY,
        param_overrides={"visits": 7},
        name="Scenario Alpha",
        description="Primary scenario",
        extras={"kind": "scenario"},
    )
    proposal = manager.proposal_manager.create_proposal(
        "proposal-alpha",
        problem.problem_id,
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
    completed = execution_service.execute_evaluation(
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

    assert {item.problem_id for item in manager.list_problems()} == {"problem-alpha"}
    assert {
        item.scenario_id for item in manager.list_scenarios(territory=DEFAULT_TERRITORY)
    } == {"scenario-alpha"}
    assert {
        item.proposal_id for item in manager.list_proposals(problem.problem_id)
    } == {proposal.proposal_id}
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
    manager, evaluator, model, execution_service = _make_manager(tmp_path)
    session_manager_module.Scenario = Scenario
    session_manager_module.Evaluation = Evaluation

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        territory=DEFAULT_TERRITORY,
        name="Problem Alpha",
        description="Primary problem",
    )
    base_scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        territory=problem.territory,
        param_overrides={"visits": 9},
        name="Draft Scenario",
        description="Transient scenario",
    )

    session = manager.create_session(
        territory=DEFAULT_TERRITORY,
        metadata={"source": "test"},
    )
    session_scenario = manager.create_session_scenario(
        session.session_id,
        base_scenario.scenario_id,
        param_overrides={"visits": 11},
    )
    running = manager.evaluation_manager.build_running_evaluation(
        "evaluation-session",
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

    reloaded_session = manager.read_session(session.session_id)
    assert reloaded_session.metadata == session.metadata
    assert reloaded_session.active_scenario_id == session_scenario.scenario_id
    expected_scenario = {
        key: value
        for key, value in session_scenario.to_dict().items()
        if not key.startswith("_")
    }
    assert (
        manager.read_session_scenario(
            session.session_id,
            session_scenario.scenario_id,
        ).to_dict()
        == expected_scenario
    )
    assert (
        manager.read_session_evaluation(
            session.session_id,
            session_scenario.scenario_id,
        ).to_dict()
        == session_evaluation.to_dict()
    )
    assert session_evaluation.state is EvaluationState.COMPLETED
    assert reloaded_session.active_scenario_id == session_scenario.scenario_id
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 11},
    }

    manager.delete_session(session.session_id)
    assert manager.list_sessions() == []


def test_manager_read_scenario_data_reuses_persisted_results(tmp_path) -> None:
    manager, evaluator, model, execution_service = _make_manager(tmp_path)

    problem = manager.problem_manager.create_problem(
        "problem-alpha",
        territory=DEFAULT_TERRITORY,
        name="Problem Alpha",
        description="Primary problem",
    )
    scenario = manager.scenario_manager.create_scenario(
        "scenario-alpha",
        territory=problem.territory,
        param_overrides={"visits": 13},
        name="Scenario Alpha",
        description="Primary scenario",
    )

    evaluation = manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        scenario.scenario_id,
    )
    completed = execution_service.execute_evaluation(
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
