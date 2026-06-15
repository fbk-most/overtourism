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
    assert [item["problem_id"] for item in response.json()] == [
        f"{tenant}_base_problem"
    ]


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
    generated_problem_id = response.json()["problem_id"]
    assert generated_problem_id
    assert generated_problem_id != "lake-cleanup"
    assert response.json()["version"] == 1
    assert response.json()["tenant"] == tenant
    assert response.json()["name"] == "Lake Cleanup"
    assert response.json()["description"] == "Reduce visitor pressure"
    assert response.json()["extras"] == {}


def test_read_problem_returns_current_version(client, tenant: str) -> None:
    response = client.get(f"/api/v2/{tenant}/problems/{tenant}_base_problem")

    assert response.status_code == 200
    assert response.json()["problem_id"] == f"{tenant}_base_problem"
    assert response.json()["version"] == 1
    assert response.json()["tenant"] == tenant


def test_update_problem_requires_matching_version_in_entity(
    client, tenant: str
) -> None:
    missing_version = client.put(
        f"/api/v2/{tenant}/problems/{tenant}_base_problem",
        json={"name": "Updated default"},
    )

    assert missing_version.status_code == 428
    assert missing_version.json() == {"detail": "Missing version in entity payload"}

    response = client.put(
        f"/api/v2/{tenant}/problems/{tenant}_base_problem",
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
    problem = manager.create_problem(
        name="Delete me",
        description="Disposable",
        extras={},
        tenant=tenant,
    )

    response = client.delete(f"/api/v2/{tenant}/problems/{problem.problem_id}")

    assert response.status_code == 200
    assert all(
        item.problem_id != problem.problem_id for item in manager.list_problems()
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
        "anonymous:tenant-alpha",
    ) == [session_id]

    delete_response = client.delete(f"/api/v2/{tenant}/problems/{problem_id}")

    assert delete_response.status_code == 200
    assert handler.session_ownership_store.list_session_ids(
        tenant,
        "anonymous:tenant-alpha",
    ) == [session_id]
