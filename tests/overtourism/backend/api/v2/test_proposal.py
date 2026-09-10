# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.manager.manager import Manager


def test_create_and_list_proposals_for_a_problem(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        json={
            "problem_id": problem_id,
            "proposal_id": "proposal-api",
            "name": "Proposal API",
            "description": "Created through the route",
            "status": "draft",
            "extras": {"channel": "api"},
            "related_scenario_ids": [base_scenario_id],
        },
    )

    assert create_response.status_code == 200
    proposal_id = create_response.json()["proposal_id"]
    assert proposal_id
    assert create_response.json()["version"] == 1
    assert create_response.json()["extras"] == {"channel": "api"}
    assert create_response.json()["related_scenario_ids"] == [base_scenario_id]

    read_response = client.get(
        f"/api/v2/{tenant}/proposals/{proposal_id}",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["related_scenario_ids"] == [base_scenario_id]

    list_response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    proposals = {item["proposal_id"]: item for item in list_response.json()}
    assert proposal_id in proposals
    assert proposals[proposal_id]["related_scenario_ids"] == [base_scenario_id]


@pytest.mark.parametrize("related_scenario_ids", [None, []])
def test_create_proposal_adds_base_scenario_when_payload_omits_it(
    client,
    tenant: str,
    problem_id: str,
    related_scenario_ids: list[str] | None,
) -> None:
    payload: dict[str, object] = {
        "problem_id": problem_id,
        "proposal_id": "proposal-base-default",
    }
    if related_scenario_ids is not None:
        payload["related_scenario_ids"] = related_scenario_ids

    response = client.post(f"/api/v2/{tenant}/proposals", json=payload)

    assert response.status_code == 200
    assert response.json()["related_scenario_ids"] == [f"{tenant}_base_scenario"]


def test_create_proposal_keeps_related_scenarios_and_adds_base(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    related_scenario = manager.scenario_manager.create_scenario(
        "scenario-linked-to-proposal",
        tenant,
        name="Linked scenario",
    )

    response = client.post(
        f"/api/v2/{tenant}/proposals",
        json={
            "problem_id": problem_id,
            "proposal_id": "proposal-with-related-scenario",
            "related_scenario_ids": [related_scenario.scenario_id],
        },
    )

    assert response.status_code == 200
    assert response.json()["related_scenario_ids"] == [
        related_scenario.scenario_id,
        f"{tenant}_base_scenario",
    ]


def test_create_proposal_rejects_problem_from_another_tenant(
    client,
    manager: Manager,
    tenant: str,
) -> None:
    foreign_problem = manager.create_problem(
        tenant="tenant-beta",
        name="Foreign problem",
    )

    response = client.post(
        f"/api/v2/{tenant}/proposals",
        json={"problem_id": foreign_problem.problem_id},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Problem '{foreign_problem.problem_id}' not found."
    }


def test_list_proposals_can_filter_by_related_scenario(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    related_scenario = manager.scenario_manager.create_scenario(
        "scenario-linked",
        tenant,
        param_overrides={"visits": 8},
        name="Linked scenario",
    )
    proposal = manager.create_proposal(
        problem_id,
        name="Linked proposal",
        status="draft",
        related_scenario_ids=[related_scenario.scenario_id],
    )

    response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id, "scenario_id": related_scenario.scenario_id},
    )

    assert response.status_code == 200
    assert [item["proposal_id"] for item in response.json()] == [proposal.proposal_id]


def test_updating_only_related_scenarios_increments_proposal_version(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    proposal = manager.create_proposal(
        problem_id,
        related_scenario_ids=[f"{tenant}_base_scenario"],
    )

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        json={"version": 1, "related_scenario_ids": []},
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert update_response.json()["related_scenario_ids"] == []

    stale_response = client.put(
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        json={"version": 1, "name": "Stale update"},
    )
    assert stale_response.status_code == 412


def test_update_and_delete_proposal_require_the_current_version(
    client,
    error_client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    proposal = manager.create_proposal(
        problem_id,
        name="Versioned proposal",
        status="draft",
        related_scenario_ids=[base_scenario_id],
    )

    missing_version = client.put(
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        params={"problem_id": problem_id},
        json={"name": "Updated proposal"},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "name": "Updated proposal",
            "status": "accepted",
            "related_scenario_ids": [],
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert update_response.json()["name"] == "Updated proposal"
    assert update_response.json()["status"] == "accepted"
    assert update_response.json()["related_scenario_ids"] == []
    assert (
        manager.relationship_manager.get_related_scenario_ids(
            proposal.proposal_id,
        )
        == []
    )
    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        params={"problem_id": problem_id},
        json={"version": 2},
    )

    assert delete_response.status_code == 200
    assert {
        proposal.proposal_id for proposal in manager.list_proposals(problem_id)
    } == {f"{tenant}_base_proposal"}


def test_proposal_write_validation_rejects_missing_related_scenarios(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"
    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        json={
            "problem_id": problem_id,
            "proposal_id": "proposal-invalid",
            "related_scenario_ids": ["missing-scenario"],
        },
    )

    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Scenario 'missing-scenario' not found."
    }

    proposal = manager.create_proposal(
        problem_id,
        name="Valid proposal",
        related_scenario_ids=[base_scenario_id],
    )

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/{proposal.proposal_id}",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "related_scenario_ids": [base_scenario_id, "missing-scenario"],
        },
    )

    assert update_response.status_code == 404
    assert update_response.json() == {
        "detail": "Scenario 'missing-scenario' not found."
    }
