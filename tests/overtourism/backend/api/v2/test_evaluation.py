# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.api.v2 import evaluation as evaluation_api
from overtourism.dt_manager.manager.manager import Manager


def test_create_and_read_stored_evaluation(
    client, tenant: str, problem_id: str
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": "default", "ensemble_size": 7},
    )

    assert create_response.status_code == 200
    assert create_response.headers["etag"] == "2"
    assert create_response.json()["scenario_id"] == "default"
    assert create_response.json()["state"] == "COMPLETED"
    assert create_response.json()["result"] == {
        "ensemble_size": 7,
        "values": {},
    }

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": "default"},
    )

    assert read_response.status_code == 200
    assert read_response.headers["etag"] == "2"
    assert (
        read_response.json()["evaluation_id"] == create_response.json()["evaluation_id"]
    )


def test_create_and_read_session_evaluation_for_a_draft(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    draft = manager.create_session_scenario(
        problem_id,
        "session-eval",
        "default",
        values={"visits": 5},
        name="Session draft",
    )

    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        headers={"Session-ID": "session-eval"},
        json={"scenario_id": draft.scenario_id, "ensemble_size": 4},
    )

    assert create_response.status_code == 200
    assert create_response.headers["etag"] == "2"
    assert create_response.json()["scenario_id"] == draft.scenario_id
    assert create_response.json()["result"] == {
        "ensemble_size": 4,
        "values": {"visits": 5},
    }

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": draft.scenario_id},
        headers={"Session-ID": "session-eval"},
    )

    assert read_response.status_code == 200
    assert (
        read_response.json()["evaluation_id"] == create_response.json()["evaluation_id"]
    )


def test_evaluation_data_returns_arranged_data_widgets_and_editable_indexes(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    manager.update_problem(problem_id, extras={"editable_indexes": ["visits"]})
    manager.update_scenario(problem_id, "default", values={"visits": 9})
    manager.evaluate_scenario(problem_id, "default", ensemble_size=3)

    monkeypatch.setattr(evaluation_api, "model_values", lambda handler: {"base": 1})
    monkeypatch.setattr(
        evaluation_api,
        "scenario_index_diffs",
        lambda handler, scenario: {"visits": "+9"},
    )

    response = client.get(
        f"/api/v2/{tenant}/evaluations/data",
        params={"problem_id": problem_id, "scenario_id": "default", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "problem_id": problem_id,
        "scenario_id": "default",
        "data": {"ensemble_size": 3, "values": {"visits": 9}},
        "index_diffs": {"visits": "+9"},
        "widgets": {
            "summary": {
                "language": "en",
                "values": {"base": 1, "visits": 9},
            }
        },
        "editable_indexes": ["visits"],
    }
