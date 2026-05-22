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
    assert create_response.headers["etag"] == "1"
    assert create_response.json()["proposal_id"] == "proposal-api"
    assert create_response.json()["extras"] == {"channel": "api"}

    list_response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    assert {item["proposal_id"] for item in list_response.json()} == {
        "default",
        "proposal-api",
    }


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
    assert missing_version.json() == {"detail": "Missing Version header"}

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/proposal-versioned",
        params={"problem_id": problem_id},
        headers={"Version": "1"},
        json={
            "name": "Updated proposal",
            "status": "accepted",
            "related_scenario_ids": [],
        },
    )

    assert update_response.status_code == 200
    assert update_response.headers["etag"] == "2"
    assert update_response.json()["name"] == "Updated proposal"
    assert update_response.json()["status"] == "accepted"
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
    assert delete_missing_version.json() == {"detail": "Missing Version header"}

    delete_response = client.delete(
        f"/api/v2/{tenant}/proposals/proposal-versioned",
        params={"problem_id": problem_id},
        headers={"Version": "2"},
    )

    assert delete_response.status_code == 200
    assert {
        proposal.proposal_id for proposal in manager.list_proposals(problem_id)
    } == {"default"}
