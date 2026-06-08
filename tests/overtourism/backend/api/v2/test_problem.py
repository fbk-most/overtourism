# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.manager import Manager


def test_list_problems_filters_by_tenant(client, manager: Manager, tenant: str) -> None:
    manager.problem_manager.create_problem(
        "tenant-beta-problem",
        tenant="tenant-beta",
        name="Other problem",
        description="Not visible from this tenant",
        extras={},
    )

    response = client.get(f"/api/v2/{tenant}/problems")

    assert response.status_code == 200
    assert [item["problem_id"] for item in response.json()] == ["default"]


def test_create_problem_returns_slugified_problem_with_version(
    client, tenant: str
) -> None:
    response = client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "name": "Lake Cleanup",
            "description": "Reduce visitor pressure",
            "extras": {"ignored": True},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "problem_id": "lake-cleanup",
        "version": 1,
        "tenant": tenant,
        "name": "Lake Cleanup",
        "description": "Reduce visitor pressure",
        "created": response.json()["created"],
        "updated": response.json()["updated"],
        "extras": {},
    }


def test_read_problem_returns_current_version(client, tenant: str) -> None:
    response = client.get(f"/api/v2/{tenant}/problems/default")

    assert response.status_code == 200
    assert response.json()["problem_id"] == "default"
    assert response.json()["version"] == 1
    assert response.json()["tenant"] == tenant


def test_update_problem_requires_matching_version_in_entity(
    client, tenant: str
) -> None:
    missing_version = client.put(
        f"/api/v2/{tenant}/problems/default",
        json={"name": "Updated default"},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    response = client.put(
        f"/api/v2/{tenant}/problems/default",
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
    client, manager: Manager, tenant: str
) -> None:
    manager.create_problem(
        "problem-delete",
        problem_kwargs={
            "tenant": tenant,
            "name": "Delete me",
            "description": "Disposable",
            "extras": {},
        },
    )

    response = client.delete(f"/api/v2/{tenant}/problems/problem-delete")

    assert response.status_code == 200
    assert all(
        problem.problem_id != "problem-delete" for problem in manager.list_problems()
    )


def test_delete_problem_removes_session_ownership_rows(
    client,
    handler,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {}},
    )

    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]
    assert handler.session_ownership_store.list_session_ids(
        tenant,
        problem_id,
        "anonymous:tenant-alpha",
    ) == [session_id]

    delete_response = client.delete(f"/api/v2/{tenant}/problems/{problem_id}")

    assert delete_response.status_code == 200
    assert (
        handler.session_ownership_store.list_session_ids(
            tenant,
            problem_id,
            "anonymous:tenant-alpha",
        )
        == []
    )
