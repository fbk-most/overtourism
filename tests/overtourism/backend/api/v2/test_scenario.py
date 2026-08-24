# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.api.utils import utils as api_utils
from overtourism.dt_manager.manager.manager import Manager


def test_list_and_read_stored_scenarios(client, tenant: str, problem_id: str) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    list_response = client.get(
        f"/api/v2/{tenant}/scenarios",
    )

    assert list_response.status_code == 200
    assert [item["scenario_id"] for item in list_response.json()] == [base_scenario_id]

    read_response = client.get(
        f"/api/v2/{tenant}/scenarios/{base_scenario_id}",
    )

    assert read_response.status_code == 200
    assert read_response.json()["scenario_id"] == base_scenario_id
    assert read_response.json()["version"] == 1


def test_list_scenarios_can_return_only_the_base_scenario(
    client,
    tenant: str,
    problem_id: str,
    manager: Manager,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    extra_scenario = manager.scenario_manager.create_scenario(
        "scenario-extra",
        tenant,
        param_overrides={"visits": 3},
        name="Extra scenario",
    )

    response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": problem_id, "base_only": True},
    )

    assert response.status_code == 200
    assert response.json()["scenario_id"] == base_scenario_id
    assert response.json()["scenario_id"] != extra_scenario.scenario_id


def test_scenario_routes_expose_index_diffs_in_extras(
    client,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    monkeypatch.setattr(
        api_utils,
        "scenario_index_diffs",
        lambda handler, scenario: {"visits": "+3"},
    )

    list_response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": problem_id},
    )
    read_response = client.get(
        f"/api/v2/{tenant}/scenarios/{base_scenario_id}",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["extras"]["index_diffs"] == {"visits": "+3"}
    assert read_response.status_code == 200
    assert read_response.json()["extras"]["index_diffs"] == {"visits": "+3"}


def test_create_stored_scenario_persists_values_and_metadata(
    client,
    tenant: str,
) -> None:
    response = client.post(
        f"/api/v2/{tenant}/scenarios",
        json={
            "name": "Created through API",
            "description": "Stored scenario payload",
            "values": {"visits": 12},
            "extras": {"channel": "api"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"]
    assert payload["name"] == "Created through API"
    assert payload["description"] == "Stored scenario payload"
    assert payload["extras"]["channel"] == "api"
    assert payload["index_values"] == [
        {"index_name": "visits", "index_value": 12, "index_type": "constant"}
    ]


def test_list_stored_scenarios_can_filter_by_related_proposal(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    related_scenario = manager.scenario_manager.create_scenario(
        "scenario-related",
        tenant,
        param_overrides={"visits": 4},
        name="Related scenario",
    )
    manager.link_scenario_to_proposal(proposal_id, related_scenario.scenario_id)

    response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": problem_id, "proposal_id": proposal_id},
    )

    assert response.status_code == 200
    assert {item["scenario_id"] for item in response.json()} == {
        related_scenario.scenario_id,
        f"{tenant}_base_scenario",
    }


def test_update_stored_scenario_requires_the_current_version(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    missing_version = client.put(
        f"/api/v2/{tenant}/scenarios/{base_scenario_id}",
        params={"problem_id": problem_id},
        json={"name": "Updated default", "values": {"visits": 11}},
    )

    assert missing_version.status_code == 400
    assert missing_version.json() == {
        "detail": "Base scenario cannot be modified or deleted."
    }


def test_session_scenario_can_be_created_updated_and_saved(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    session_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {}},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    create_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": base_scenario_id,
            "name": "Draft scenario",
            "description": "Scenario under discussion",
            "values": {"visits": 7},
            "extras": {"stage": "draft"},
        },
    )

    assert create_response.status_code == 200
    draft_id = create_response.json()["scenario_id"]
    assert draft_id
    assert create_response.json()["version"] == 1

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["extras"] == {"index_diffs": {}}

    update_response = client.put(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "name": "Draft scenario updated",
            "values": {"visits": 9},
            "extras": {"stage": "review"},
        },
    )

    assert update_response.status_code == 405

    save_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
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
    assert save_response.json()["version"] == 1
    assert save_response.json()["name"] == "Saved scenario"
    assert (
        manager.relationship_manager.get_related_scenario_ids(proposal_id)[-1]
        == draft_id
    )
    assert session_id in {
        session.session_id for session in manager.session_manager.list_sessions()
    }


def test_session_scenario_routes_expose_index_diffs_in_extras(
    client,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    session_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {}},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    monkeypatch.setattr(
        api_utils,
        "scenario_index_diffs",
        lambda handler, scenario: {"visits": "+7"},
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": base_scenario_id,
            "name": "Draft scenario",
            "values": {"visits": 7},
            "extras": {"stage": "draft"},
        },
    )

    assert create_response.status_code == 200
    draft_id = create_response.json()["scenario_id"]
    assert create_response.json()["extras"] == {
        "index_diffs": {"visits": "+7"},
    }

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["extras"] == {"index_diffs": {"visits": "+7"}}


def test_session_scenario_can_be_deleted_without_affecting_stored_scenarios(
    client,
    tenant: str,
    problem_id: str,
    manager: Manager,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    session_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {}},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    draft_response = client.post(
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": base_scenario_id,
            "values": {"visits": 3},
            "name": "Disposable draft",
        },
    )
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["scenario_id"]

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/sessions/{session_id}/scenarios/{draft_id}",
        params={"problem_id": problem_id},
        json={"version": 1},
    )

    assert delete_response.status_code == 405
    assert [
        scenario.scenario_id
        for scenario in manager.session_manager.list_session_scenarios(session_id)
    ] == [draft_id]


def test_delete_stored_scenario_removes_it_from_the_problem(
    client,
    error_client,
    tenant: str,
    problem_id: str,
    manager: Manager,
) -> None:
    scenario = manager.scenario_manager.create_scenario(
        "scenario-delete",
        tenant,
        param_overrides={"visits": 5},
        name="Scenario delete",
    )

    delete_response = error_client.request(
        "DELETE",
        f"/api/v2/{tenant}/scenarios/{scenario.scenario_id}",
        params={"problem_id": problem_id},
        json={"version": 1},
    )

    assert delete_response.status_code == 200
    assert scenario.scenario_id not in {
        item.scenario_id for item in manager.list_scenarios(tenant)
    }
