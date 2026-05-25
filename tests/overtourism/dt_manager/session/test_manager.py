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


def test_session_manager_exposes_the_transient_session_workflow(tmp_path) -> None:
    manager, evaluator, model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    session_id = "session-1"
    manager.create_problem(
        problem_id,
        problem_kwargs={
            "name": "Problem Alpha",
            "description": "Primary problem",
        },
    )

    session = manager.session_manager.create_session(
        problem_id,
        session_id,
        metadata={"source": "test"},
    )
    draft = manager.session_manager.create_session_scenario(
        problem_id,
        session_id,
        default_config.scenario_id,
        values={"visits": 8},
    )
    evaluation = manager.session_manager.create_session_evaluation(
        problem_id,
        session_id,
        draft.scenario_id,
        ensemble_size=5,
    )

    assert manager.session_manager.read_session(problem_id, session_id) is session
    assert (
        manager.session_manager.read_session_scenario(problem_id, session_id) is draft
    )
    assert (
        manager.session_manager.read_session_evaluation(problem_id, session_id)
        is evaluation
    )
    assert evaluation.state is EvaluationState.COMPLETED
    assert evaluator.evaluate_calls[-1] == {
        "model": model,
        "ensemble_size": 5,
        "values": {"visits": 8},
    }


def test_session_manager_can_save_a_session_draft_with_its_evaluation(
    tmp_path,
) -> None:
    manager, _evaluator, _model = _make_manager(tmp_path)
    default_config = BaseConfig()

    problem_id = "problem-alpha"
    session_id = "session-1"
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
        related_scenario_ids=[default_config.scenario_id],
    )

    draft = manager.session_manager.evaluate_session(
        problem_id,
        session_id,
        default_config.scenario_id,
        values={"visits": 11},
        ensemble_size=4,
    )

    saved = manager.session_manager.save_session_scenario(
        problem_id,
        session_id,
        scenario_id=draft.scenario_id,
        name="Saved Draft",
        proposal_id=proposal.proposal_id,
    )

    assert saved.scenario_id == draft.scenario_id
    assert manager.read_scenario(problem_id, draft.scenario_id).name == "Saved Draft"
    assert manager.problem_manager.get_related_scenario_ids(
        problem_id,
        proposal.proposal_id,
    ) == [default_config.scenario_id, draft.scenario_id]
    assert manager.session_manager.read_session(problem_id, session_id).drafts == {}

    with pytest.raises(ScenarioDoesNotExist):
        manager.session_manager.read_session_scenario(problem_id, session_id)
    with pytest.raises(EvaluationDoesNotExist):
        manager.session_manager.read_session_evaluation(problem_id, session_id)
