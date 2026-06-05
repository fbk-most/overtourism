# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.manager import Manager


def test_list_and_read_stored_scenarios(client, tenant: str, problem_id: str) -> None:
    list_response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    assert [item["scenario_id"] for item in list_response.json()] == ["default"]

    read_response = client.get(
        f"/api/v2/{tenant}/scenarios/default",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["scenario_id"] == "default"
    assert read_response.json()["version"] == 1


def test_update_stored_scenario_requires_the_current_version(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    missing_version = client.put(
        f"/api/v2/{tenant}/scenarios/default",
        params={"problem_id": problem_id},
        json={"name": "Updated default", "values": {"visits": 11}},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    update_response = client.put(
        f"/api/v2/{tenant}/scenarios/default",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "name": "Updated default",
            "description": "Updated through the route",
            "values": {"visits": 11},
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert update_response.json()["name"] == "Updated default"
    assert update_response.json()["index_values"] == [
        {
            "index_name": "visits",
            "index_value": 11,
            "index_type": "constant",
        }
    ]


def test_session_scenario_can_be_created_updated_and_saved(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/sessions/session-1/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": "default",
            "name": "Draft scenario",
            "description": "Scenario under discussion",
            "values": {"visits": 7},
            "extras": {"stage": "draft"},
        },
    )

    assert create_response.status_code == 200
    draft_id = create_response.json()["scenario_id"]
    assert draft_id.startswith("default_session-1_")
    assert create_response.json()["version"] == 1

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/session-1/scenarios/{draft_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["extras"] == {"stage": "draft"}

    update_response = client.put(
        f"/api/v2/{tenant}/sessions/session-1/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "name": "Draft scenario updated",
            "values": {"visits": 9},
            "extras": {"stage": "review"},
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert update_response.json()["name"] == "Draft scenario updated"
    assert update_response.json()["extras"] == {"stage": "review"}

    save_response = client.post(
        f"/api/v2/{tenant}/sessions/session-1/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={
            "version": 2,
            "name": "Saved scenario",
            "description": "Persisted after review",
            "proposal_id": proposal_id,
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["scenario_id"] == draft_id
    assert save_response.json()["version"] == 2
    assert save_response.json()["name"] == "Saved scenario"
    assert (
        manager.problem_manager.get_related_scenario_ids(problem_id, proposal_id)[-1]
        == draft_id
    )
    assert manager.session_manager.list_session_scenarios(problem_id, "session-1") == []


def test_session_scenario_can_be_deleted_without_affecting_stored_scenarios(
    client,
    tenant: str,
    problem_id: str,
    manager: Manager,
) -> None:
    draft_response = client.post(
        f"/api/v2/{tenant}/sessions/session-delete/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": "default",
            "values": {"visits": 3},
            "name": "Disposable draft",
        },
    )
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["scenario_id"]

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/sessions/session-delete/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={"version": 1},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "message": "Session scenario deleted successfully"
    }
    assert (
        manager.session_manager.list_session_scenarios(
            problem_id,
            "session-delete",
        )
        == []
    )


def test_delete_stored_scenario_removes_it_from_the_problem(
    client,
    tenant: str,
    problem_id: str,
    manager: Manager,
) -> None:
    scenario = manager.create_scenario(
        problem_id,
        scenario_id="scenario-delete",
        session_id="seed",
        values={"visits": 5},
        name="Scenario delete",
    )

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/scenarios/{scenario.scenario_id}",
        params={"problem_id": problem_id},
        json={"version": 1},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Scenario deleted successfully"}
    assert {
        stored_scenario.scenario_id
        for stored_scenario in manager.list_scenarios(problem_id)
    } == {"default"}
