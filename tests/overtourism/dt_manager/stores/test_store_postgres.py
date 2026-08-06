# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from overtourism.dt_manager.stores.classes.sql.store import SQLStore

POSTGRES_URL = "postgresql+psycopg://postgres:123@localhost:5432/postgres"


@pytest.fixture
def postgres_sql_store() -> Iterator[SQLStore]:
    store = SQLStore(POSTGRES_URL)
    cleanup_sql = text(
        "TRUNCATE TABLE proposal_scenario_relationship, evaluations, proposals, scenarios, problems RESTART IDENTITY CASCADE"
    )

    with store.engine.begin() as connection:
        connection.execute(cleanup_sql)

    try:
        yield store
    finally:
        with store.engine.begin() as connection:
            connection.execute(cleanup_sql)


def test_sql_store_round_trip_and_cascade_deletes_on_postgres(
    postgres_sql_store: SQLStore,
    problem_payload,
    scenario_payload,
    proposal_payload,
    evaluation_payload,
) -> None:
    postgres_sql_store.save_problem(problem_payload)
    postgres_sql_store.save_scenario(scenario_payload)
    postgres_sql_store.save_proposal(proposal_payload)
    postgres_sql_store.save_relationships(
        [
            {
                "proposal_id": proposal_payload["proposal_id"],
                "scenario_id": scenario_payload["scenario_id"],
            }
        ]
    )
    postgres_sql_store.save_evaluation(evaluation_payload)

    assert (
        postgres_sql_store.load_problem(problem_payload["problem_id"])
        == problem_payload
    )
    assert postgres_sql_store.load_scenarios() == [scenario_payload]
    assert postgres_sql_store.load_proposals() == [proposal_payload]
    assert postgres_sql_store.load_relationships() == [
        {
            "proposal_id": proposal_payload["proposal_id"],
            "scenario_id": scenario_payload["scenario_id"],
        }
    ]
    assert postgres_sql_store.load_evaluations() == [evaluation_payload]

    postgres_sql_store.delete_problem(problem_payload["problem_id"])

    assert postgres_sql_store.load_problems() == []
    assert postgres_sql_store.load_scenarios() == [scenario_payload]
    assert postgres_sql_store.load_proposals() == []
    assert postgres_sql_store.load_relationships() == []
    assert postgres_sql_store.load_evaluations() == [evaluation_payload]

    postgres_sql_store.delete_scenario(scenario_payload["scenario_id"])

    assert postgres_sql_store.load_scenarios() == []
    assert postgres_sql_store.load_evaluations() == []


def test_evaluation_result_is_persisted_as_binary_on_postgres(
    postgres_sql_store: SQLStore,
    problem_payload,
    scenario_payload,
) -> None:
    postgres_sql_store.save_problem(problem_payload)
    postgres_sql_store.save_scenario(scenario_payload)

    result = {
        "notes": ["lorem ipsum dolor sit amet" * 50 for _ in range(20)],
        "metrics": {
            "visits": 1234,
            "crowding": 0.87,
            "detail": [f"value-{index}" for index in range(200)],
        },
    }
    evaluation = {
        "evaluation_id": "evaluation-binary",
        "scenario_id": scenario_payload["scenario_id"],
        "type": "default",
        "state": "COMPLETED",
        "started": "2026-05-15T08:10:00Z",
        "finished": "2026-05-15T08:11:00Z",
        "result": result,
    }

    postgres_sql_store.save_evaluation(evaluation)

    with postgres_sql_store.engine.connect() as connection:
        raw_result = connection.exec_driver_sql(
            "select result from evaluations where evaluation_id = %s",
            (evaluation["evaluation_id"],),
        ).scalar_one()

    assert isinstance(raw_result, (bytes, bytearray, memoryview))
    assert len(bytes(raw_result)) < len(json.dumps(result).encode("utf-8"))
