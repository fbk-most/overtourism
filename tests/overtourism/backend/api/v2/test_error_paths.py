# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any


def _raise_runtime_error(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("boom")


def test_problem_routes_return_a_friendly_422_validation_payload(
    client,
    tenant: str,
) -> None:
    response = client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "description": "Missing required name",
            "extras": {},
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Validation failed",
        "errors": [
            {
                "field": "body.name",
                "message": "Field required",
                "type": "missing",
            }
        ],
    }


def test_problem_routes_surface_not_found_and_internal_errors(
    client,
    error_client,
    handler,
    tenant: str,
) -> None:
    read_response = client.get(f"/api/v2/{tenant}/problems/missing-problem")
    assert read_response.status_code == 404
    assert read_response.json() == {"detail": "Problem 'missing-problem' not found."}

    update_response = client.put(
        f"/api/v2/{tenant}/problems/missing-problem",
        json={"version": 1, "name": "Updated"},
    )
    assert update_response.status_code == 404

    delete_response = client.delete(f"/api/v2/{tenant}/problems/missing-problem")
    assert delete_response.status_code == 404

    handler.manager.create_problem = _raise_runtime_error
    create_response = error_client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "name": "Broken",
            "description": "Will fail",
            "extras": {},
        },
    )
    assert create_response.status_code == 500


def test_proposal_routes_return_404_for_missing_problem_and_proposal(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    list_response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 200
    assert list_response.json() == []

    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        json={"problem_id": "missing-problem", "proposal_id": "proposal-x"},
    )
    assert create_response.status_code == 404
    assert create_response.json() == {"detail": "Problem 'missing-problem' not found."}

    read_response = client.get(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
    )
    update_response = client.put(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
        json={"version": 1, "name": "Updated"},
    )
    delete_response = client.delete(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
    )

    for response in (read_response, update_response, delete_response):
        assert response.status_code == 404
        assert response.json() == {"detail": "Proposal 'missing-proposal' not found."}


def test_scenario_routes_return_404_for_missing_entities(
    client,
    error_client,
    tenant: str,
    problem_id: str,
) -> None:
    list_response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 200
    assert [item["scenario_id"] for item in list_response.json()] == [
        f"{tenant}_base_scenario"
    ]

    create_response = client.post(
        f"/api/v2/{tenant}/sessions/session-404/scenarios",
        params={"problem_id": problem_id},
        json={"base_scenario_id": "missing-scenario"},
    )
    assert create_response.status_code == 404
    assert create_response.json() == {"detail": "Session 'session-404' not found."}

    read_response = client.get(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404

    update_response = error_client.put(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
        json={"version": 1, "name": "Updated"},
    )
    assert update_response.status_code == 404

    save_response = client.post(
        f"/api/v2/{tenant}/sessions/session-404/scenarios/missing-scenario",
        params={"problem_id": problem_id},
        json={"version": 1, "name": "Save failed"},
    )
    assert save_response.status_code == 404

    delete_response = error_client.delete(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
    )
    assert delete_response.status_code == 404


def test_session_routes_return_404_for_missing_problem_or_session(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": "missing-problem"},
        json={"metadata": {}},
    )
    assert create_response.status_code == 200
    assert create_response.json()["metadata"] == {}

    list_response = client.get(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 200
    assert list_response.json() == [create_response.json()]

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/missing-session",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404
    assert read_response.json() == {"detail": "Session 'missing-session' not found."}

    delete_response = client.delete(
        f"/api/v2/{tenant}/sessions/missing-session",
        params={"problem_id": problem_id},
    )
    assert delete_response.status_code == 404


def test_evaluation_routes_return_404_for_missing_entities(
    client,
    error_client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": "missing-scenario"},
    )
    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Scenario 'missing-scenario' not found."
    }

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations/missing-evaluation",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404

    data_response = client.get(
        f"/api/v2/{tenant}/evaluations/missing-evaluation/data",
        params={"problem_id": problem_id},
    )
    assert data_response.status_code == 404

    update_response = client.put(
        f"/api/v2/{tenant}/evaluations/missing-evaluation",
        params={"problem_id": problem_id},
        json={"version": 1, "ensemble_size": 4},
    )
    assert update_response.status_code == 404

    delete_response = client.delete(
        f"/api/v2/{tenant}/evaluations/missing-evaluation",
        params={"problem_id": problem_id},
    )
    assert delete_response.status_code == 404

    session_response = client.post(
        f"/api/v2/{tenant}/sessions/missing-session/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": "missing-scenario"},
    )
    assert session_response.status_code == 404

    session_data_response = client.get(
        f"/api/v2/{tenant}/sessions/missing-session/evaluations/missing-evaluation/data",
        params={"problem_id": problem_id},
    )
    assert session_data_response.status_code == 404
