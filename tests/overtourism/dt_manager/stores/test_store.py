# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json

import pytest
from sqlalchemy import inspect

from overtourism.dt_manager.utils.exception import EntityDoesNotExist


def test_problem_round_trip_and_delete_problem(
    sql_store,
    problem_payload,
    other_problem_payload,
    scenario_payload,
    proposal_payload,
    evaluation_payload,
) -> None:
    problem = dict(problem_payload, created="2026-05-15T08:10:00Z")
    other_problem = dict(other_problem_payload, created="2026-05-15T08:20:00Z")

    sql_store.save_problem(problem)
    sql_store.save_problem(other_problem)
    sql_store.save_scenario(scenario_payload)
    sql_store.save_proposal(proposal_payload)
    sql_store.save_relationships(
        [
            {
                "proposal_id": proposal_payload["proposal_id"],
                "scenario_id": scenario_payload["scenario_id"],
            }
        ]
    )
    sql_store.save_evaluation(evaluation_payload)

    assert [item["problem_id"] for item in sql_store.load_problems()] == [
        other_problem["problem_id"],
        problem["problem_id"],
    ]
    assert sql_store.load_problem(problem["problem_id"]) == problem
    assert sql_store.load_problem(other_problem["problem_id"]) == other_problem
    assert sql_store.load_scenarios() == [scenario_payload]
    assert sql_store.load_proposals() == [proposal_payload]
    assert sql_store.load_relationships() == [
        {
            "proposal_id": proposal_payload["proposal_id"],
            "scenario_id": scenario_payload["scenario_id"],
        }
    ]
    assert sql_store.load_evaluations() == [evaluation_payload]

    sql_store.delete_problem(problem["problem_id"])

    assert [item["problem_id"] for item in sql_store.load_problems()] == [
        other_problem["problem_id"],
    ]
    assert sql_store.load_scenarios() == [scenario_payload]
    assert sql_store.load_proposals() == []
    assert sql_store.load_relationships() == []
    assert sql_store.load_evaluations() == [evaluation_payload]


def test_entity_round_trip_sorted_listings_and_relationship_filters(
    sql_store,
    problem_payload,
    scenario_payload,
    other_scenario_payload,
    proposal_payload,
    other_proposal_payload,
    evaluation_payload,
    other_evaluation_payload,
) -> None:
    scenario = dict(scenario_payload, created="2026-05-15T08:10:00Z")
    other_scenario = dict(other_scenario_payload, created="2026-05-15T08:20:00Z")
    proposal = dict(proposal_payload, created="2026-05-15T08:10:00Z")
    other_proposal = dict(other_proposal_payload, created="2026-05-15T08:20:00Z")
    evaluation = dict(evaluation_payload, started="2026-05-15T08:10:00Z")
    other_evaluation = dict(
        other_evaluation_payload,
        started="2026-05-15T08:20:00Z",
    )

    sql_store.save_problem(problem_payload)
    sql_store.save_scenario(other_scenario)
    sql_store.save_scenario(scenario)
    sql_store.save_proposal(other_proposal)
    sql_store.save_proposal(proposal)
    sql_store.save_relationships(
        [
            {
                "proposal_id": other_proposal["proposal_id"],
                "scenario_id": other_scenario["scenario_id"],
            },
            {
                "proposal_id": proposal["proposal_id"],
                "scenario_id": scenario["scenario_id"],
            },
        ]
    )
    sql_store.save_evaluation(other_evaluation)
    sql_store.save_evaluation(evaluation)

    assert [item["scenario_id"] for item in sql_store.load_scenarios()] == [
        other_scenario["scenario_id"],
        scenario["scenario_id"],
    ]
    assert sql_store.load_scenario(scenario["scenario_id"]) == scenario
    assert [
        item["scenario_id"]
        for item in sql_store.load_scenarios(proposal_id=proposal["proposal_id"])
    ] == [
        scenario["scenario_id"],
    ]

    assert [item["proposal_id"] for item in sql_store.load_proposals()] == [
        other_proposal["proposal_id"],
        proposal["proposal_id"],
    ]
    assert sql_store.load_proposal(proposal["proposal_id"]) == proposal
    assert [
        item["proposal_id"]
        for item in sql_store.load_proposals(scenario_id=scenario["scenario_id"])
    ] == [
        proposal["proposal_id"],
    ]

    assert sorted(
        (item["proposal_id"], item["scenario_id"])
        for item in sql_store.load_relationships()
    ) == sorted(
        [
            (other_proposal["proposal_id"], other_scenario["scenario_id"]),
            (proposal["proposal_id"], scenario["scenario_id"]),
        ]
    )

    assert [item["evaluation_id"] for item in sql_store.load_evaluations()] == [
        other_evaluation["evaluation_id"],
        evaluation["evaluation_id"],
    ]
    assert sql_store.load_evaluation(evaluation["evaluation_id"]) == evaluation
    assert [
        item["evaluation_id"]
        for item in sql_store.load_evaluations(scenario_id=scenario["scenario_id"])
    ] == [
        evaluation["evaluation_id"],
    ]

    sql_store.delete_evaluation(other_evaluation["evaluation_id"])
    sql_store.delete_scenario(other_scenario["scenario_id"])
    sql_store.delete_proposal(other_proposal["proposal_id"])

    assert [item["scenario_id"] for item in sql_store.load_scenarios()] == [
        scenario["scenario_id"],
    ]
    assert [item["proposal_id"] for item in sql_store.load_proposals()] == [
        proposal["proposal_id"],
    ]
    assert sql_store.load_relationships() == [
        {
            "proposal_id": proposal["proposal_id"],
            "scenario_id": scenario["scenario_id"],
        }
    ]
    assert [item["evaluation_id"] for item in sql_store.load_evaluations()] == [
        evaluation["evaluation_id"],
    ]

    with pytest.raises(EntityDoesNotExist):
        sql_store.load_scenario(other_scenario["scenario_id"])
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_proposal(other_proposal["proposal_id"])
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_evaluation(other_evaluation["evaluation_id"])


def test_missing_entities_raise(sql_store) -> None:
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_problem("missing-problem")
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_scenario("missing-scenario")
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_proposal("missing-proposal")
    with pytest.raises(EntityDoesNotExist):
        sql_store.load_evaluation("missing-evaluation")

    sql_store.delete_problem("missing-problem")
    sql_store.delete_scenario("missing-scenario")
    sql_store.delete_proposal("missing-proposal")
    sql_store.delete_evaluation("missing-evaluation")

    assert sql_store.load_relationships() == []


def test_sqlite_schema_defines_indexes_for_common_read_paths(sql_store) -> None:
    inspector = inspect(sql_store.engine)

    index_columns = {
        index["name"]: tuple(index["column_names"])
        for table_name in [
            "problems",
            "proposals",
            "scenarios",
            "proposal_scenario_relationship",
            "evaluations",
        ]
        for index in inspector.get_indexes(table_name)
    }

    assert index_columns["ix_problems_tenant_created"] == ("tenant", "created")
    assert index_columns["ix_proposals_problem_id_created"] == ("problem_id", "created")
    assert index_columns["ix_scenarios_tenant_created"] == ("tenant", "created")
    assert index_columns["ix_proposal_scenario_relationship_scenario_id"] == (
        "scenario_id",
    )
    assert index_columns["ix_evaluations_scenario_id_started"] == (
        "scenario_id",
        "started",
    )


def test_evaluation_results_are_compressed_at_rest_and_restored_on_read(
    sql_store,
    problem_payload,
    scenario_payload,
) -> None:
    sql_store.save_problem(problem_payload)
    sql_store.save_scenario(scenario_payload)

    result = {
        "notes": ["lorem ipsum dolor sit amet" * 50 for _ in range(20)],
        "metrics": {
            "visits": 1234,
            "crowding": 0.87,
            "detail": [f"value-{index}" for index in range(200)],
        },
    }
    evaluation = {
        "evaluation_id": "evaluation-compressed",
        "scenario_id": scenario_payload["scenario_id"],
        "type": "default",
        "state": "COMPLETED",
        "started": "2026-05-15T08:10:00Z",
        "finished": "2026-05-15T08:11:00Z",
        "result": result,
    }
    expected_evaluation = dict(evaluation, version=0, session_id=None)

    sql_store.save_evaluation(evaluation)

    assert sql_store.load_evaluation(evaluation["evaluation_id"]) == expected_evaluation

    with sql_store.engine.connect() as connection:
        raw_result = connection.exec_driver_sql(
            "select result from evaluations where evaluation_id = ?",
            (evaluation["evaluation_id"],),
        ).scalar_one()

    assert isinstance(raw_result, (bytes, bytearray, memoryview))
    assert len(bytes(raw_result)) < len(json.dumps(result).encode("utf-8"))
