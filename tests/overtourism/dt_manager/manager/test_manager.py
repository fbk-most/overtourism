# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ScenarioDoesNotExist,
    SessionDoesNotExist,
)

from tests.overtourism.dt_manager.conftest import FakeModelEvaluator


def _make_manager(
    tmp_path,
    *,
    evaluator: FakeModelEvaluator | None = None,
    base_problem_config: BaseConfig | None = None,
) -> tuple[Manager, FakeModelEvaluator, SimpleNamespace]:
    evaluator = FakeModelEvaluator() if evaluator is None else evaluator
    model = SimpleNamespace(name="fake-model")
    manager = Manager(
        model=model,
        model_evaluator=evaluator,
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        base_problem_config=base_problem_config,
    )
    return manager, evaluator, model


def test_manager_bootstraps_default_problem_when_store_is_empty(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
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
        for scenario in manager.list_scenarios(default_config.problem_id)
    ] == [default_config.scenario_id]
    assert [
        proposal.proposal_id
        for proposal in manager.list_proposals(default_config.problem_id)
    ] == [default_config.proposal_id]
    assert manager.problem_manager.get_related_scenario_ids(
        default_config.problem_id,
        default_config.proposal_id,
    ) == [default_config.scenario_id]

    evaluation_manager = manager.evaluation_managers[default_config.problem_id]
    evaluations = evaluation_manager.list_evaluations()
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.state is EvaluationState.COMPLETED
    assert evaluation.scenario_id == default_config.scenario_id
    assert evaluation.result.to_dict() == {"ensemble_size": 20, "values": {}}

    assert evaluator.evaluate_calls == [
        {"model": model, "ensemble_size": 20, "values": {}}
    ]
    assert manager.read_scenario_data(
        default_config.problem_id, default_config.scenario_id
    ) == {
        "ensemble_size": 20,
        "values": {},
    }


def test_create_problem_workflow_creates_default_child_graph(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
            "extras": {"region": "tn"},
        },
    )

    problem = manager.read_problem(problem_id)
    assert problem.problem_id == problem_id
    assert problem.tenant == manager.base_problem_config.tenant
    assert problem.name == "Problem Alpha"
    assert problem.description == "Primary problem"
    assert problem.extras == {"region": "tn"}

    assert [
        scenario.scenario_id for scenario in manager.list_scenarios(problem_id)
    ] == [manager.base_problem_config.scenario_id]
    assert manager.list_proposals(problem_id) == []

    evaluation_manager = manager.evaluation_managers[problem_id]
    evaluations = evaluation_manager.list_evaluations()
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.state is EvaluationState.COMPLETED
    assert evaluation.scenario_id == manager.base_problem_config.scenario_id
    assert evaluation.result.to_dict() == {"ensemble_size": 20, "values": {}}

    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 20,
        "values": {},
    }
    assert manager.read_scenario_data(
        problem_id, manager.base_problem_config.scenario_id
    ) == {
        "ensemble_size": 20,
        "values": {},
    }


def test_create_and_delete_workflows_manage_relationships(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    proposal = manager.create_proposal(
        problem_id,
        proposal_id="proposal-alpha",
        name="Proposal Alpha",
        status="draft",
        related_scenario_ids=[manager.base_problem_config.scenario_id],
    )
    assert proposal.proposal_id == "proposal-alpha"
    assert manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [manager.base_problem_config.scenario_id]

    scenario = manager.create_scenario(
        problem_id,
        scenario_id="scenario-alpha",
        session_id="session-1",
        values={"visits": 7},
        name="Scenario Alpha",
        proposal_id=proposal.proposal_id,
    )
    assert scenario.scenario_id.startswith("scenario-alpha_session-1_")
    assert [entry.to_dict() for entry in scenario.index_values] == [
        {
            "index_name": "visits",
            "index_value": 7,
            "index_type": "constant",
        }
    ]
    assert manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [
        manager.base_problem_config.scenario_id,
        scenario.scenario_id,
    ]
    assert manager.read_scenario_data(problem_id, scenario.scenario_id) == {
        "ensemble_size": 20,
        "values": {"visits": 7},
    }
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 20,
        "values": {"visits": 7},
    }

    evaluation_manager = manager.evaluation_managers[problem_id]
    assert len(evaluation_manager.list_evaluations()) == 2

    manager.delete_scenario(problem_id, scenario.scenario_id)
    assert scenario.scenario_id not in {
        item.scenario_id for item in manager.list_scenarios(problem_id)
    }
    assert evaluation_manager.list_evaluations(scenario.scenario_id) == []
    assert manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [manager.base_problem_config.scenario_id]

    manager.delete_proposal(problem_id, proposal.proposal_id)
    assert proposal.proposal_id not in {
        item.proposal_id for item in manager.list_proposals(problem_id)
    }
    assert manager.problem_manager.get_relationships(problem_id) == []


def test_session_workflow_can_be_resumed_and_closed(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    session_id = "session-1"
    session_scenario = manager.evaluate_session(
        problem_id,
        session_id,
        default_config.scenario_id,
        values={"visits": 9},
        ensemble_size=7,
    )

    resumed_scenario, resumed_evaluation = manager.resume_session(
        problem_id, session_id
    )
    assert resumed_scenario is session_scenario
    assert resumed_evaluation.scenario_id == session_scenario.scenario_id
    assert resumed_evaluation.state is EvaluationState.COMPLETED
    assert resumed_evaluation.result.to_dict() == {
        "ensemble_size": 7,
        "values": {"visits": 9},
    }
    assert session_scenario.scenario_id.startswith(
        f"{default_config.scenario_id}_{session_id}_"
    )
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 7,
        "values": {"visits": 9},
    }

    assert manager.has_session(problem_id, session_id)
    assert manager.read_session(problem_id, session_id).active_scenario_id == (
        session_scenario.scenario_id
    )

    manager.close_session(problem_id, session_id)

    assert not manager.has_session(problem_id, session_id)
    assert [
        scenario.scenario_id for scenario in manager.list_scenarios(problem_id)
    ] == [
        default_config.scenario_id,
    ]
    assert [
        evaluation.scenario_id
        for evaluation in manager.evaluation_managers[problem_id].list_evaluations()
    ] == [default_config.scenario_id]

    with pytest.raises(SessionDoesNotExist):
        manager.read_session(problem_id, session_id)
    with pytest.raises(SessionDoesNotExist):
        manager.read_session_scenario(problem_id, session_id)
    with pytest.raises(SessionDoesNotExist):
        manager.read_session_evaluation(problem_id, session_id)


def test_session_workflow_can_be_promoted_and_reloaded(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    proposal = manager.create_proposal(
        problem_id,
        proposal_id="proposal-alpha",
        related_scenario_ids=[manager.base_problem_config.scenario_id],
    )

    session_id = "session-1"
    session_scenario = manager.evaluate_session(
        problem_id,
        session_id,
        default_config.scenario_id,
        values={"visits": 11},
        ensemble_size=5,
    )

    promoted = manager.save_session_scenario(
        problem_id,
        session_id,
        name="Session Scenario",
        description="Session description",
        extras={"kind": "session"},
        proposal_id=proposal.proposal_id,
    )

    assert promoted is session_scenario
    assert promoted.name == "Session Scenario"
    assert promoted.description == "Session description"
    assert promoted.extras == {"kind": "session"}
    assert [
        scenario.scenario_id for scenario in manager.list_scenarios(problem_id)
    ] == [
        default_config.scenario_id,
        promoted.scenario_id,
    ]
    assert [
        proposal_item.proposal_id
        for proposal_item in manager.list_proposals(problem_id)
    ] == [
        proposal.proposal_id,
    ]
    assert manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [default_config.scenario_id, promoted.scenario_id]
    assert [
        evaluation.scenario_id
        for evaluation in manager.evaluation_managers[problem_id].list_evaluations()
    ] == [default_config.scenario_id, promoted.scenario_id]
    assert manager.read_scenario_data(problem_id, promoted.scenario_id) == {
        "ensemble_size": 5,
        "values": {"visits": 11},
    }
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 11},
    }

    assert manager.read_session(problem_id, session_id).drafts == {}

    with pytest.raises(ScenarioDoesNotExist):
        manager.read_session_scenario(problem_id, session_id)
    with pytest.raises(EvaluationDoesNotExist):
        manager.read_session_evaluation(problem_id, session_id)

    reloaded_evaluator = FakeModelEvaluator()
    reloaded_manager, _ignored_evaluator, _ignored_model = _make_manager(
        tmp_path,
        evaluator=reloaded_evaluator,
    )

    assert {problem.problem_id for problem in reloaded_manager.list_problems()} == {
        default_config.problem_id,
        problem_id,
    }
    reloaded_problem = reloaded_manager.read_problem(problem_id)
    assert reloaded_problem.name == "Problem Alpha"
    assert reloaded_problem.tenant == manager.base_problem_config.tenant
    assert (
        reloaded_manager.read_problem(default_config.problem_id).name
        == default_config.problem_name
    )
    assert [
        scenario.scenario_id for scenario in reloaded_manager.list_scenarios(problem_id)
    ] == [
        default_config.scenario_id,
        promoted.scenario_id,
    ]
    assert [
        proposal_item.proposal_id
        for proposal_item in reloaded_manager.list_proposals(problem_id)
    ] == [
        proposal.proposal_id,
    ]
    assert reloaded_manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [default_config.scenario_id, promoted.scenario_id]

    loaded_session_evaluation = next(
        evaluation
        for evaluation in reloaded_manager.evaluation_managers[
            problem_id
        ].list_evaluations()
        if evaluation.scenario_id == promoted.scenario_id
    )
    assert loaded_session_evaluation.result.to_dict() == {
        "ensemble_size": 5,
        "values": {"visits": 11},
    }
    assert reloaded_manager.read_scenario_data(problem_id, promoted.scenario_id) == {
        "ensemble_size": 5,
        "values": {"visits": 11},
    }


def test_session_scenario_can_be_updated_and_re_evaluated(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    session_id = "session-1"
    session_scenario = manager.create_session_scenario(
        problem_id,
        session_id,
        default_config.scenario_id,
        values={"visits": 9},
    )
    first_evaluation = manager.create_session_evaluation(
        problem_id,
        session_id,
        session_scenario.scenario_id,
        ensemble_size=7,
    )

    assert first_evaluation.state is EvaluationState.COMPLETED
    assert first_evaluation.result.to_dict() == {
        "ensemble_size": 7,
        "values": {"visits": 9},
    }

    updated_session_scenario = manager.update_session_scenario(
        problem_id,
        session_id,
        session_scenario.scenario_id,
        values={"visits": 12},
    )

    assert updated_session_scenario.scenario_id == session_scenario.scenario_id
    assert [entry.to_dict() for entry in updated_session_scenario.index_values] == [
        {
            "index_name": "visits",
            "index_value": 12,
            "index_type": "constant",
        }
    ]

    with pytest.raises(EvaluationDoesNotExist):
        manager.read_session_evaluation(problem_id, session_id)

    second_evaluation = manager.create_session_evaluation(
        problem_id,
        session_id,
        session_scenario.scenario_id,
        ensemble_size=4,
    )

    assert second_evaluation.state is EvaluationState.COMPLETED
    assert second_evaluation.result.to_dict() == {
        "ensemble_size": 4,
        "values": {"visits": 12},
    }
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 4,
        "values": {"visits": 12},
    }

    promoted = manager.save_session_scenario(
        problem_id,
        session_id,
        scenario_id=session_scenario.scenario_id,
        name="Session Scenario",
    )

    assert promoted.scenario_id == session_scenario.scenario_id
    assert promoted.name == "Session Scenario"
    assert manager.read_scenario(problem_id, promoted.scenario_id).to_dict() == (
        promoted.to_dict()
    )

    stored_evaluations = manager.evaluation_managers[problem_id].list_evaluations(
        promoted.scenario_id
    )
    assert len(stored_evaluations) == 1
    assert stored_evaluations[0].result.to_dict() == {
        "ensemble_size": 4,
        "values": {"visits": 12},
    }
    assert manager.read_session(problem_id, session_id).drafts == {}


def test_session_state_tracks_multiple_drafts(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    session = manager.create_session(
        problem_id,
        "session-1",
        metadata={"title": "Exploration"},
    )
    first_draft = manager.create_session_scenario(
        problem_id,
        session.session_id,
        default_config.scenario_id,
        values={"visits": 8},
    )
    second_draft = manager.create_session_scenario(
        problem_id,
        session.session_id,
        default_config.scenario_id,
        values={"visits": 13},
    )

    assert [
        draft.scenario_id
        for draft in manager.list_session_scenarios(problem_id, session.session_id)
    ] == [first_draft.scenario_id, second_draft.scenario_id]
    assert manager.read_session(problem_id, session.session_id).active_scenario_id == (
        second_draft.scenario_id
    )

    first_evaluation = manager.create_session_evaluation(
        problem_id,
        session.session_id,
        first_draft.scenario_id,
        ensemble_size=3,
    )
    second_evaluation = manager.create_session_evaluation(
        problem_id,
        session.session_id,
        second_draft.scenario_id,
        ensemble_size=6,
    )

    assert first_evaluation.result.to_dict() == {
        "ensemble_size": 3,
        "values": {"visits": 8},
    }
    assert second_evaluation.result.to_dict() == {
        "ensemble_size": 6,
        "values": {"visits": 13},
    }
    assert manager.read_session_evaluation(
        problem_id,
        session.session_id,
        first_draft.scenario_id,
    ).result.to_dict() == {
        "ensemble_size": 3,
        "values": {"visits": 8},
    }
    assert manager.read_session(problem_id, session.session_id).evaluations[
        second_draft.scenario_id
    ].result.to_dict() == {
        "ensemble_size": 6,
        "values": {"visits": 13},
    }

    manager.delete_session(problem_id, session.session_id)

    with pytest.raises(SessionDoesNotExist):
        manager.read_session(problem_id, session.session_id)


def test_manager_reloads_existing_graph_from_store(tmp_path) -> None:
    manager, _evaluator, _model = _make_manager(tmp_path)

    problem_id = "problem-alpha"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )
    proposal = manager.create_proposal(
        problem_id,
        proposal_id="proposal-alpha",
        related_scenario_ids=[manager.base_problem_config.scenario_id],
    )
    scenario = manager.create_scenario(
        problem_id,
        scenario_id="scenario-alpha",
        session_id="session-1",
        values={"visits": 7},
        proposal_id=proposal.proposal_id,
    )

    reloaded_evaluator = FakeModelEvaluator()
    reloaded_manager, _ignored_evaluator, _ignored_model = _make_manager(
        tmp_path,
        evaluator=reloaded_evaluator,
    )

    assert {problem.problem_id for problem in reloaded_manager.list_problems()} == {
        manager.base_problem_config.problem_id,
        problem_id,
    }
    reloaded_problem = reloaded_manager.read_problem(problem_id)
    assert reloaded_problem.name == "Problem Alpha"
    assert reloaded_problem.tenant == manager.base_problem_config.tenant
    assert [
        scenario_data.scenario_id
        for scenario_data in reloaded_manager.list_scenarios(problem_id)
    ] == [
        manager.base_problem_config.scenario_id,
        scenario.scenario_id,
    ]
    assert [
        proposal_data.proposal_id
        for proposal_data in reloaded_manager.list_proposals(problem_id)
    ] == [
        proposal.proposal_id,
    ]
    assert reloaded_manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [
        manager.base_problem_config.scenario_id,
        scenario.scenario_id,
    ]
    assert len(reloaded_manager.evaluation_managers[problem_id].list_evaluations()) == 2
    assert reloaded_manager.read_scenario_data(problem_id, scenario.scenario_id) == {
        "ensemble_size": 20,
        "values": {"visits": 7},
    }
