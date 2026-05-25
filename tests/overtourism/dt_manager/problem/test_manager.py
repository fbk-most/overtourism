# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.sql.store import SQLStore


def _make_manager(tmp_path) -> ProblemManager:
    return ProblemManager(SQLStore(f"sqlite:///{tmp_path / 'store.db'}"))


def test_problem_manager_persists_problem_state_directly_to_store(tmp_path) -> None:
    manager = _make_manager(tmp_path)

    manager.create_problem(
        "problem-alpha",
        tenant="molveno",
        name="Problem Alpha",
        description="Primary problem",
        extras={"region": "tn"},
    )

    problem = manager.read_problem("problem-alpha")
    assert problem.problem_id == "problem-alpha"
    assert problem.tenant == "molveno"
    assert problem.name == "Problem Alpha"
    assert problem.description == "Primary problem"
    assert problem.extras == {"region": "tn"}

    problem.name = "Cached only"
    assert manager.read_problem("problem-alpha").name == "Problem Alpha"

    manager.update_problem(
        "problem-alpha",
        name="Updated problem",
        extras={"theme": "mobility"},
    )
    assert manager.read_problem("problem-alpha").name == "Updated problem"
    assert manager.read_problem("problem-alpha").extras == {
        "region": "tn",
        "theme": "mobility",
    }

    assert [item.problem_id for item in manager.list_problems()] == [
        "problem-alpha",
    ]

    reloaded_manager = _make_manager(tmp_path)
    assert reloaded_manager.read_problem("problem-alpha").name == "Updated problem"


def test_relationships_are_persisted_without_cache(tmp_path) -> None:
    manager = _make_manager(tmp_path)

    problem_id = "problem-alpha"
    proposal_id = "proposal-alpha"
    scenario_id = "scenario-alpha"

    manager.create_problem(problem_id)

    scenario = Scenario.create_default(scenario_id, problem_id=problem_id)
    proposal = Proposal.create_default(proposal_id, problem_id=problem_id)

    manager.store.save_scenario(problem_id, scenario_id, scenario.to_dict())
    manager.store.save_proposal(problem_id, proposal_id, proposal.to_dict())

    manager.link_scenario_proposal(problem_id, proposal_id, scenario_id)

    assert manager.store.load_relationships(problem_id) == [
        {"proposal_id": proposal_id, "scenario_id": scenario_id},
    ]
    assert manager.get_relationships(problem_id) == [
        {"proposal_id": proposal_id, "scenario_id": scenario_id},
    ]
    assert manager.get_related_scenario_ids(problem_id, proposal_id) == [
        scenario_id,
    ]

    reloaded_manager = _make_manager(tmp_path)
    assert reloaded_manager.get_related_scenario_ids(problem_id, proposal_id) == [
        scenario_id,
    ]


def test_relationship_mutations_keep_links_normalized(tmp_path) -> None:
    manager = _make_manager(tmp_path)

    problem_id = "problem-alpha"
    proposal_id = "proposal-alpha"
    other_proposal_id = "proposal-beta"
    scenario_ids = [
        "scenario-alpha",
        "scenario-beta",
        "scenario-gamma",
        "scenario-delta",
        "scenario-other",
    ]

    manager.create_problem(problem_id)
    manager.store.save_proposal(
        problem_id,
        proposal_id,
        Proposal.create_default(proposal_id, problem_id=problem_id).to_dict(),
    )
    manager.store.save_proposal(
        problem_id,
        other_proposal_id,
        Proposal.create_default(other_proposal_id, problem_id=problem_id).to_dict(),
    )
    for scenario_id in scenario_ids:
        manager.store.save_scenario(
            problem_id,
            scenario_id,
            Scenario.create_default(scenario_id, problem_id=problem_id).to_dict(),
        )

    manager.link_scenario_proposal(problem_id, other_proposal_id, "scenario-other")

    manager.set_related_scenario_ids(
        problem_id,
        proposal_id,
        ["", "scenario-beta", "scenario-beta", "scenario-gamma"],
    )

    assert manager.get_relationships(problem_id) == [
        {"proposal_id": proposal_id, "scenario_id": "scenario-beta"},
        {"proposal_id": proposal_id, "scenario_id": "scenario-gamma"},
        {"proposal_id": other_proposal_id, "scenario_id": "scenario-other"},
    ]

    manager.link_scenario_proposal(problem_id, proposal_id, "scenario-gamma")
    manager.link_scenario_proposal(problem_id, proposal_id, "scenario-delta")
    manager.link_scenario_proposal(problem_id, proposal_id, "")

    assert manager.get_relationships(problem_id) == [
        {"proposal_id": proposal_id, "scenario_id": "scenario-beta"},
        {"proposal_id": proposal_id, "scenario_id": "scenario-delta"},
        {"proposal_id": proposal_id, "scenario_id": "scenario-gamma"},
        {"proposal_id": other_proposal_id, "scenario_id": "scenario-other"},
    ]

    manager.unlink_scenario_proposal(problem_id, proposal_id, "scenario-gamma")

    assert manager.get_relationships(problem_id) == [
        {"proposal_id": proposal_id, "scenario_id": "scenario-beta"},
        {"proposal_id": proposal_id, "scenario_id": "scenario-delta"},
        {"proposal_id": other_proposal_id, "scenario_id": "scenario-other"},
    ]
