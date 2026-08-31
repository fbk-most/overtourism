# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.manager.manager import Manager


@pytest.fixture(autouse=True)
def mock_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "overtourism.backend.api.v2.evaluation.call_executor",
        lambda tenant, param_overrides: {"values": param_overrides},
    )
    monkeypatch.setattr(
        "overtourism.backend.api.v2.session.call_executor",
        lambda tenant, param_overrides: {"values": param_overrides},
    )


def _create_owned_session_and_draft(
    client,
    tenant: str,
    problem_id: str,
    *,
    values: dict[str, int],
    name: str,
    session_metadata: dict | None = None,
) -> tuple[str, str]:
    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {} if session_metadata is None else session_metadata},
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    draft_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": f"{tenant}_base_scenario",
            "param_overrides": values,
            "name": name,
        },
    )
    assert draft_response.status_code == 200
    return session_id, draft_response.json()["scenario_id"]


def test_create_and_read_stored_evaluation(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": base_scenario_id, "ensemble_size": 7},
    )

    assert create_response.status_code == 200
    assert create_response.json()["version"] == 1
    assert create_response.json()["scenario_id"] == base_scenario_id
    assert create_response.json()["state"] == "COMPLETED"
    assert "result" not in create_response.json()
    evaluation_id = create_response.json()["evaluation_id"]

    list_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": base_scenario_id},
    )

    assert list_response.status_code == 200
    assert evaluation_id in [item["evaluation_id"] for item in list_response.json()]

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["evaluation_id"] == evaluation_id
    assert read_response.json()["scenario_id"] == base_scenario_id
    assert read_response.json()["version"] == 1
    assert "result" not in read_response.json()


def test_create_evaluation_persists_failed_state_when_executor_fails(
    client,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    def fail_executor(tenant: str, param_overrides: dict) -> dict:
        raise RuntimeError("executor failed")

    monkeypatch.setattr(
        "overtourism.backend.api.v2.evaluation.call_executor",
        fail_executor,
    )

    response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": f"{tenant}_base_scenario"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "FAILED"
    evaluation_id = response.json()["evaluation_id"]

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["state"] == "FAILED"


def test_list_evaluations_filters_by_tenant(
    client,
    manager: Manager,
    tenant: str,
) -> None:
    foreign_problem = manager.create_problem(
        name="Foreign problem",
        description="Not visible here",
        extras={},
        tenant="tenant-beta",
    )
    foreign_scenario = manager.create_scenario(
        tenant="tenant-beta",
        param_overrides={"visits": 4},
        name="Foreign scenario",
    )
    foreign_evaluation = manager.evaluation_manager.create_evaluation(
        "foreign-evaluation",
        foreign_scenario.scenario_id,
    )

    response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": foreign_problem.problem_id},
    )

    assert response.status_code == 200
    assert all(
        item["evaluation_id"] != foreign_evaluation.evaluation_id
        for item in response.json()
    )


def test_list_evaluations_excludes_session_evaluations(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    session_id, draft_id = _create_owned_session_and_draft(
        client,
        tenant,
        problem_id,
        values={"visits": 5},
        name="Session evaluation draft",
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id},
    )
    assert create_response.status_code == 200
    evaluation_id = create_response.json()["evaluation_id"]

    response = client.get(f"/api/v2/{tenant}/evaluations")

    assert response.status_code == 200
    assert evaluation_id not in {item["evaluation_id"] for item in response.json()}


def test_stored_evaluation_can_be_updated_and_deleted_with_payload_version(
    client,
    error_client,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": base_scenario_id, "ensemble_size": 2},
    )
    evaluation_id = create_response.json()["evaluation_id"]

    missing_version = error_client.put(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"ensemble_size": 5},
    )

    assert missing_version.status_code == 428

    update_response = client.put(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 1, "ensemble_size": 5},
    )

    assert update_response.status_code == 200
    assert update_response.json()["evaluation_id"] == evaluation_id
    assert update_response.json()["version"] == 2

    delete_missing_version = error_client.delete(
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert delete_missing_version.status_code == 428

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 1},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Evaluation deleted successfully"}
    assert (
        error_client.get(
            f"/api/v2/{tenant}/evaluations/{evaluation_id}",
            params={"problem_id": problem_id},
        ).status_code
        == 500
    )


def test_create_and_read_session_evaluation_for_a_draft(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    session_id, draft_id = _create_owned_session_and_draft(
        client,
        tenant,
        problem_id,
        values={"visits": 5},
        name="Session draft",
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id, "ensemble_size": 4},
    )

    assert create_response.status_code == 200
    assert create_response.json()["version"] == 2
    assert create_response.json()["scenario_id"] == draft_id
    assert "result" not in create_response.json()
    evaluation_id = create_response.json()["evaluation_id"]

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["version"] == 2
    assert read_response.json()["evaluation_id"] == evaluation_id
    assert "result" not in read_response.json()


def test_saving_session_scenario_publishes_its_evaluation(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    session_id, draft_id = _create_owned_session_and_draft(
        client,
        tenant,
        problem_id,
        values={"visits": 5},
        name="Session draft",
    )

    evaluation_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id},
    )
    assert evaluation_response.status_code == 200
    evaluation_id = evaluation_response.json()["evaluation_id"]

    save_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={"version": 2},
    )

    assert save_response.status_code == 200
    assert save_response.json()["session_id"] is None

    public_evaluations_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": draft_id},
    )
    assert public_evaluations_response.status_code == 200
    public_evaluation = next(
        item
        for item in public_evaluations_response.json()
        if item["evaluation_id"] == evaluation_id
    )
    assert public_evaluation["session_id"] is None


def test_session_evaluation_can_be_updated_and_deleted(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    session_id, draft_id = _create_owned_session_and_draft(
        client,
        tenant,
        problem_id,
        values={"visits": 6},
        name="Session draft",
    )
    create_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id, "ensemble_size": 3},
    )
    evaluation_id = create_response.json()["evaluation_id"]

    update_response = client.put(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 2, "ensemble_size": 8},
    )

    assert update_response.status_code == 405

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations/{evaluation_id}",
        params={"problem_id": problem_id},
        json={"version": 3},
    )

    assert delete_response.status_code == 405


def test_evaluation_data_returns_arranged_data(
    client,
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    manager.update_scenario(base_scenario_id, param_overrides={"visits": 9})
    evaluation = handler.manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        base_scenario_id,
    )
    evaluation = handler.execution_manager_registry.get(tenant).execute_evaluation(
        evaluation,
        manager.read_scenario(base_scenario_id),
        ensemble_size=3,
    )
    manager.evaluation_manager.save_evaluation(evaluation)

    response = client.get(
        f"/api/v2/{tenant}/evaluations/{evaluation.evaluation_id}/data",
        params=[
            ("problem_id", problem_id),
            ("params", "ensemble_size"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "evaluation_id": evaluation.evaluation_id,
        "scenario_id": base_scenario_id,
        "data": {"ensemble_size": 3, "values": {"visits": 9}},
    }


def test_session_evaluation_data_returns_arranged_data(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    session_id, draft_id = _create_owned_session_and_draft(
        client,
        tenant,
        problem_id,
        values={"visits": 12},
        name="Session draft",
    )
    evaluation_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id, "ensemble_size": 6},
    )
    assert evaluation_response.status_code == 200
    evaluation_id = evaluation_response.json()["evaluation_id"]

    response = client.get(
        f"/api/v2/{tenant}/sessions/{session_id}/evaluations/{evaluation_id}/data",
        params=[
            ("problem_id", problem_id),
            ("params", "ensemble_size"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "evaluation_id": evaluation_id,
        "scenario_id": draft_id,
        "data": {"values": {"visits": 12}},
    }
