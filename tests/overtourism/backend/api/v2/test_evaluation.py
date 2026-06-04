# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

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
    assert create_response.json()["version"] == 2
    assert create_response.json()["scenario_id"] == "default"
    assert create_response.json()["state"] == "COMPLETED"
    assert "result" not in create_response.json()
    evaluation_id = create_response.json()["evaluation_id"]

    list_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": "default"},
    )

    assert list_response.status_code == 200
    assert evaluation_id in [item["evaluation_id"] for item in list_response.json()]

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["version"] == 2
    assert read_response.json()["evaluation_id"] == evaluation_id
    assert "result" not in read_response.json()


def test_stored_evaluation_can_be_updated_and_deleted_with_payload_version(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": "default", "ensemble_size": 2},
    )
    evaluation_id = create_response.json()["evaluation_id"]

    missing_version = client.put(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"ensemble_size": 5},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    update_response = client.put(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 2, "ensemble_size": 5},
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 3
    assert "result" not in update_response.json()

    delete_missing_version = client.delete(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert delete_missing_version.status_code == 428

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 3},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Evaluation deleted successfully"}
    assert (
        client.get(
            f"/api/v2/{tenant}/evaluations/{evaluation_id}",
            params={"problem_id": problem_id},
        ).status_code
        == 404
    )


def test_create_and_read_session_evaluation_for_a_draft(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    draft = manager.session_manager.create_session_scenario(
        problem_id,
        "session-eval",
        "default",
        values={"visits": 5},
        name="Session draft",
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions/session-eval/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft.scenario_id, "ensemble_size": 4},
    )

    assert create_response.status_code == 200
    assert create_response.json()["version"] == 2
    assert create_response.json()["scenario_id"] == draft.scenario_id
    assert "result" not in create_response.json()
    evaluation_id = create_response.json()["evaluation_id"]

    list_response = client.get(
        f"/api/v2/{tenant}/sessions/session-eval/evaluations",
        params={"problem_id": problem_id, "scenario_id": draft.scenario_id},
    )

    assert list_response.status_code == 200
    assert [item["evaluation_id"] for item in list_response.json()] == [evaluation_id]

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/session-eval/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["version"] == 2
    assert read_response.json()["evaluation_id"] == evaluation_id
    assert "result" not in read_response.json()


def test_session_evaluation_can_be_updated_and_deleted(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    draft = manager.session_manager.create_session_scenario(
        problem_id,
        "session-update",
        "default",
        values={"visits": 6},
        name="Session draft",
    )
    create_response = client.post(
        f"/api/v2/{tenant}/sessions/session-update/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft.scenario_id, "ensemble_size": 3},
    )
    evaluation_id = create_response.json()["evaluation_id"]

    update_response = client.put(
        f"/api/v2/{tenant}/sessions/session-update/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 2, "ensemble_size": 8},
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 3
    assert "result" not in update_response.json()

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/sessions/session-update/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 3},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "message": "Session evaluation deleted successfully"
    }


def test_evaluation_data_returns_arranged_data(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    manager.update_scenario(problem_id, "default", values={"visits": 9})
    evaluation = manager.evaluate_scenario(problem_id, "default", ensemble_size=3)

    response = client.get(
        f"/api/v2/{tenant}/evaluations/{evaluation.evaluation_id}/data",
        params=[
            ("problem_id", problem_id),
            ("params", "ensemble_size"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "problem_id": problem_id,
        "evaluation_id": evaluation.evaluation_id,
        "scenario_id": "default",
        "data": {"ensemble_size": 3},
    }


def test_session_evaluation_data_returns_arranged_data(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    draft = manager.session_manager.create_session_scenario(
        problem_id,
        "session-data",
        "default",
        values={"visits": 12},
        name="Session draft",
    )
    evaluation = manager.session_manager.create_session_evaluation(
        problem_id,
        "session-data",
        draft.scenario_id,
        ensemble_size=6,
    )

    response = client.get(
        f"/api/v2/{tenant}/sessions/session-data/evaluations/{evaluation.evaluation_id}/data",
        params=[
            ("problem_id", problem_id),
            ("params", "ensemble_size"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "problem_id": problem_id,
        "evaluation_id": evaluation.evaluation_id,
        "scenario_id": draft.scenario_id,
        "data": {"ensemble_size": 6},
    }
