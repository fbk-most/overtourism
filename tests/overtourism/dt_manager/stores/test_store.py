# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
    ScenarioDoesNotExist,
)


def test_problem_round_trip_and_delete_problem(
    sql_store,
    problem_payload,
    other_problem_payload,
    scenario_payload,
    proposal_payload,
    evaluation_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    other_problem_id = other_problem_payload["problem_id"]

    sql_store.save_problem(problem_id, problem_payload)
    sql_store.save_scenario(
        problem_id,
        scenario_payload["scenario_id"],
        scenario_payload,
    )
    sql_store.save_proposal(
        problem_id,
        proposal_payload["proposal_id"],
        proposal_payload,
    )
    sql_store.save_relationships(
        problem_id,
        [
            {
                "proposal_id": proposal_payload["proposal_id"],
                "scenario_id": scenario_payload["scenario_id"],
            }
        ],
    )
    sql_store.save_evaluation(
        problem_id,
        evaluation_payload["evaluation_id"],
        evaluation_payload,
    )
    sql_store.save_problem(other_problem_id, other_problem_payload)

    assert [item["problem_id"] for item in sql_store.load_problems()] == [
        problem_id,
        other_problem_id,
    ]
    assert sql_store.load_problem(problem_id) == problem_payload
    assert sql_store.load_problem(other_problem_id) == other_problem_payload
    assert sql_store.load_scenarios(problem_id) == [scenario_payload]
    assert sql_store.load_proposals(problem_id) == [proposal_payload]
    assert sql_store.load_relationships(problem_id) == [
        {
            "proposal_id": proposal_payload["proposal_id"],
            "scenario_id": scenario_payload["scenario_id"],
        }
    ]
    assert sql_store.load_evaluations(problem_id) == [evaluation_payload]

    sql_store.delete_problem(problem_id)

    assert [item["problem_id"] for item in sql_store.load_problems()] == [
        other_problem_id,
    ]
    assert sql_store.load_scenarios(problem_id) == []
    assert sql_store.load_proposals(problem_id) == []
    assert sql_store.load_evaluations(problem_id) == []


def test_entity_round_trip_and_sorted_listings(
    sql_store,
    problem_payload,
    scenario_payload,
    other_scenario_payload,
    proposal_payload,
    other_proposal_payload,
    evaluation_payload,
    other_evaluation_payload,
) -> None:
    problem_id = problem_payload["problem_id"]

    sql_store.save_problem(problem_id, problem_payload)
    sql_store.save_scenario(
        problem_id,
        other_scenario_payload["scenario_id"],
        other_scenario_payload,
    )
    sql_store.save_scenario(
        problem_id,
        scenario_payload["scenario_id"],
        scenario_payload,
    )

    sql_store.save_proposal(
        problem_id,
        other_proposal_payload["proposal_id"],
        other_proposal_payload,
    )
    sql_store.save_proposal(
        problem_id,
        proposal_payload["proposal_id"],
        proposal_payload,
    )
    sql_store.save_relationships(
        problem_id,
        [
            {
                "proposal_id": other_proposal_payload["proposal_id"],
                "scenario_id": other_scenario_payload["scenario_id"],
            },
            {
                "proposal_id": proposal_payload["proposal_id"],
                "scenario_id": scenario_payload["scenario_id"],
            },
        ],
    )

    sql_store.save_evaluation(
        problem_id,
        other_evaluation_payload["evaluation_id"],
        other_evaluation_payload,
    )
    sql_store.save_evaluation(
        problem_id,
        evaluation_payload["evaluation_id"],
        evaluation_payload,
    )

    assert [item["scenario_id"] for item in sql_store.load_scenarios(problem_id)] == [
        scenario_payload["scenario_id"],
        other_scenario_payload["scenario_id"],
    ]
    assert (
        sql_store.load_scenario(problem_id, scenario_payload["scenario_id"])
        == scenario_payload
    )

    assert [item["proposal_id"] for item in sql_store.load_proposals(problem_id)] == [
        proposal_payload["proposal_id"],
        other_proposal_payload["proposal_id"],
    ]
    assert (
        sql_store.load_proposal(problem_id, proposal_payload["proposal_id"])
        == proposal_payload
    )
    assert sql_store.load_relationships(problem_id) == [
        {
            "proposal_id": proposal_payload["proposal_id"],
            "scenario_id": scenario_payload["scenario_id"],
        },
        {
            "proposal_id": other_proposal_payload["proposal_id"],
            "scenario_id": other_scenario_payload["scenario_id"],
        },
    ]

    assert [
        item["evaluation_id"] for item in sql_store.load_evaluations(problem_id)
    ] == [
        evaluation_payload["evaluation_id"],
        other_evaluation_payload["evaluation_id"],
    ]
    assert (
        sql_store.load_evaluation(problem_id, evaluation_payload["evaluation_id"])
        == evaluation_payload
    )

    sql_store.delete_evaluation(problem_id, other_evaluation_payload["evaluation_id"])
    sql_store.delete_scenario(problem_id, other_scenario_payload["scenario_id"])
    sql_store.delete_proposal(problem_id, other_proposal_payload["proposal_id"])

    assert [item["scenario_id"] for item in sql_store.load_scenarios(problem_id)] == [
        scenario_payload["scenario_id"],
    ]
    assert [item["proposal_id"] for item in sql_store.load_proposals(problem_id)] == [
        proposal_payload["proposal_id"],
    ]
    assert sql_store.load_relationships(problem_id) == [
        {
            "proposal_id": proposal_payload["proposal_id"],
            "scenario_id": scenario_payload["scenario_id"],
        },
    ]
    assert [
        item["evaluation_id"] for item in sql_store.load_evaluations(problem_id)
    ] == [
        evaluation_payload["evaluation_id"],
    ]

    with pytest.raises(ScenarioDoesNotExist):
        sql_store.load_scenario(problem_id, other_scenario_payload["scenario_id"])
    with pytest.raises(EvaluationDoesNotExist):
        sql_store.load_evaluation(problem_id, other_evaluation_payload["evaluation_id"])


def test_identifier_mismatch_raises_value_error(
    sql_store,
    problem_payload,
    scenario_payload,
    proposal_payload,
    evaluation_payload,
) -> None:
    problem_id = problem_payload["problem_id"]

    with pytest.raises(
        ValueError,
        match="Scenario identifiers do not match the provided arguments",
    ):
        sql_store.save_scenario(problem_id, "scenario-wrong", scenario_payload)

    with pytest.raises(
        ValueError,
        match="Proposal identifiers do not match the provided arguments",
    ):
        sql_store.save_proposal(problem_id, "proposal-wrong", proposal_payload)

    with pytest.raises(
        ValueError,
        match="Evaluation identifiers do not match the provided arguments",
    ):
        sql_store.save_evaluation(problem_id, "evaluation-wrong", evaluation_payload)


def test_missing_entities_raise(sql_store) -> None:
    with pytest.raises(FileNotFoundError):
        sql_store.load_problem("missing-problem")
    with pytest.raises(FileNotFoundError):
        sql_store.load_relationships("missing-problem")

    with pytest.raises(ScenarioDoesNotExist):
        sql_store.load_scenario("missing-problem", "missing-scenario")
    with pytest.raises(ScenarioDoesNotExist):
        sql_store.delete_scenario("missing-problem", "missing-scenario")
    with pytest.raises(ProposalDoesNotExist):
        sql_store.load_proposal("missing-problem", "missing-proposal")
    with pytest.raises(ProposalDoesNotExist):
        sql_store.delete_proposal("missing-problem", "missing-proposal")
    with pytest.raises(EvaluationDoesNotExist):
        sql_store.load_evaluation("missing-problem", "missing-evaluation")
    with pytest.raises(EvaluationDoesNotExist):
        sql_store.delete_evaluation("missing-problem", "missing-evaluation")
