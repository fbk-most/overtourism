# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.manager import Manager
from overtourism.overtourism.backend_extension.api.models.problem import (
    OvertourismPostProblemData,
    OvertourismProblemData,
    OvertourismUpdateProblemData,
)


def test_overtourism_problem_models_do_not_expose_group_metadata() -> None:
    post_data = OvertourismPostProblemData(
        name="Problem",
        description="Problem description",
        groups=["legacy-group"],
    )
    problem_data = OvertourismProblemData(
        problem_id="problem",
        territory="territory-alpha",
        groups=["legacy-group"],
        editable_indexes=["visits"],
    )
    update_data = OvertourismUpdateProblemData(groups=["legacy-group"])

    assert "groups" not in post_data.model_dump()
    assert "groups" not in problem_data.model_dump()
    assert "editable_indexes" not in problem_data.model_dump()
    assert "groups" not in update_data.model_dump()


def test_list_problems_filters_by_territory(
    client, manager: Manager, territory: str
) -> None:
    manager.problem_manager.create_problem(
        "territory-beta-problem",
        territory="territory-beta",
        name="Other problem",
        description="Not visible from this territory",
        extras={},
    )

    response = client.get(f"/api/{territory}/problems")

    assert response.status_code == 200
    assert [item["problem_id"] for item in response.json()] == [
        f"{territory}_base_problem"
    ]


def test_create_problem_returns_slugified_problem_with_version(
    client, territory: str
) -> None:
    response = client.post(
        f"/api/{territory}/problems",
        json={
            "name": "Lake Cleanup",
            "description": "Reduce visitor pressure",
            "extras": {"ignored": True},
        },
    )

    assert response.status_code == 200
    generated_problem_id = response.json()["problem_id"]
    assert generated_problem_id
    assert generated_problem_id != "lake-cleanup"
    assert response.json()["version"] == 1
    assert response.json()["territory"] == territory
    assert response.json()["name"] == "Lake Cleanup"
    assert response.json()["description"] == "Reduce visitor pressure"
    assert response.json()["extras"] == {"ignored": True}


def test_read_problem_returns_current_version(client, territory: str) -> None:
    response = client.get(f"/api/{territory}/problems/{territory}_base_problem")

    assert response.status_code == 200
    assert response.json()["problem_id"] == f"{territory}_base_problem"
    assert response.json()["version"] == 1
    assert response.json()["territory"] == territory


def test_read_problem_rejects_cross_territory_access(
    client,
    manager: Manager,
    territory: str,
) -> None:
    foreign_problem = manager.create_problem(
        name="Foreign problem",
        description="Not visible here",
        extras={},
        territory="territory-beta",
    )

    response = client.get(f"/api/{territory}/problems/{foreign_problem.problem_id}")

    assert response.status_code == 404


def test_update_problem_requires_matching_version_in_entity(
    client, territory: str
) -> None:
    missing_version = client.put(
        f"/api/{territory}/problems/{territory}_base_problem",
        json={"name": "Updated default"},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    response = client.put(
        f"/api/{territory}/problems/{territory}_base_problem",
        json={
            "version": 1,
            "name": "Updated default",
            "description": "Updated description",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated default"
    assert response.json()["description"] == "Updated description"
    assert response.json()["version"] == 2


def test_delete_problem_removes_it_from_the_store(
    client, manager: Manager, territory: str
) -> None:
    problem = manager.create_problem(
        name="Delete me",
        description="Disposable",
        extras={},
        territory=territory,
    )
    manager.update_problem(problem.problem_id, name="Delete me, updated")

    response = client.request(
        "DELETE",
        f"/api/{territory}/problems/{problem.problem_id}",
        json={"version": 2},
    )

    assert response.status_code == 200
    assert all(
        item.problem_id != problem.problem_id for item in manager.list_problems()
    )


def test_delete_problem_keeps_owned_sessions(
    client,
    handler,
    territory: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/{territory}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {}},
    )

    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]
    assert (
        handler.manager.read_session(session_id).owner_id == "anonymous:territory-alpha"
    )

    delete_response = client.request(
        "DELETE",
        f"/api/{territory}/problems/{problem_id}",
        json={"version": 1},
    )

    assert delete_response.status_code == 200
    assert (
        handler.manager.read_session(session_id).owner_id == "anonymous:territory-alpha"
    )
