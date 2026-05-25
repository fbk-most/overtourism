# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.manager import Manager


def test_create_and_list_proposals_for_a_problem(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id},
        json={
            "proposal_id": "proposal-api",
            "name": "Proposal API",
            "description": "Created through the route",
            "status": "draft",
            "extras": {"channel": "api"},
            "related_scenario_ids": ["default"],
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["proposal_id"] == "proposal-api"
    assert create_response.json()["version"] == 1
    assert create_response.json()["extras"] == {"channel": "api"}
    assert create_response.json()["related_scenario_ids"] == ["default"]

    read_response = client.get(
        f"/api/v2/{tenant}/proposals/proposal-api",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["related_scenario_ids"] == ["default"]

    list_response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    proposals = {item["proposal_id"]: item for item in list_response.json()}
    assert set(proposals) == {"default", "proposal-api"}
    assert proposals["proposal-api"]["related_scenario_ids"] == ["default"]


def test_update_and_delete_proposal_require_the_current_version(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    manager.create_proposal(
        problem_id,
        proposal_id="proposal-versioned",
        name="Versioned proposal",
        status="draft",
        related_scenario_ids=["default"],
    )

    missing_version = client.put(
        f"/api/v2/{tenant}/proposals/proposal-versioned",
        params={"problem_id": problem_id},
        json={"name": "Updated proposal"},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/proposal-versioned",
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
        manager.problem_manager.get_related_scenario_ids(
            problem_id,
            "proposal-versioned",
        )
        == []
    )

    delete_missing_version = client.delete(
        f"/api/v2/{tenant}/proposals/proposal-versioned",
        params={"problem_id": problem_id},
    )

    assert delete_missing_version.status_code == 428
    assert delete_missing_version.json() == {
        "detail": "Missing version in entity payload"
    }

    delete_response = client.request(
        "DELETE",
        f"/api/v2/{tenant}/proposals/proposal-versioned",
        params={"problem_id": problem_id},
        json={"version": 2},
    )

    assert delete_response.status_code == 200
    assert {
        proposal.proposal_id for proposal in manager.list_proposals(problem_id)
    } == {"default"}


def test_proposal_write_validation_rejects_missing_related_scenarios(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id},
        json={
            "proposal_id": "proposal-invalid",
            "related_scenario_ids": ["missing-scenario"],
        },
    )

    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Scenario 'missing-scenario' not found for problem 'default'"
    }

    manager.create_proposal(
        problem_id,
        proposal_id="proposal-valid",
        name="Valid proposal",
        related_scenario_ids=["default"],
    )

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/proposal-valid",
        params={"problem_id": problem_id},
        json={
            "version": 1,
            "related_scenario_ids": ["default", "missing-scenario"],
        },
    )

    assert update_response.status_code == 404
    assert update_response.json() == {
        "detail": "Scenario 'missing-scenario' not found for problem 'default'"
    }
