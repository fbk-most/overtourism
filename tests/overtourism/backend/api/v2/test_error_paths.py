# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any


def _raise_runtime_error(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("boom")


def test_problem_routes_surface_not_found_and_internal_errors(
    client,
    error_client,
    handler,
    tenant: str,
) -> None:
    read_response = client.get(f"/api/v2/{tenant}/problems/missing-problem")
    assert read_response.status_code == 404
    assert read_response.json() == {
        "detail": "Problem 'missing-problem' not found for tenant 'tenant-alpha'"
    }

    update_response = client.put(
        f"/api/v2/{tenant}/problems/missing-problem",
        headers={"Version": "1"},
        json={"problem_name": "Updated"},
    )
    assert update_response.status_code == 404

    delete_response = client.delete(f"/api/v2/{tenant}/problems/missing-problem")
    assert delete_response.status_code == 404

    handler.manager.create_problem = _raise_runtime_error
    create_response = error_client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "problem_name": "Broken",
            "problem_description": "Will fail",
            "extras": {},
        },
    )
    assert create_response.status_code == 500


def test_proposal_routes_return_404_for_missing_problem_and_proposal(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    list_response = client.get(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 404

    create_response = client.post(
        f"/api/v2/{tenant}/proposals",
        params={"problem_id": "missing-problem"},
        json={"proposal_id": "proposal-x"},
    )
    assert create_response.status_code == 404

    read_response = client.get(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404
    assert read_response.json() == {
        "detail": "Proposal 'missing-proposal' not found for problem 'default'"
    }

    update_response = client.put(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
        headers={"Version": "1"},
        json={"name": "Updated"},
    )
    assert update_response.status_code == 404

    delete_response = client.delete(
        f"/api/v2/{tenant}/proposals/missing-proposal",
        params={"problem_id": problem_id},
        headers={"Version": "1"},
    )
    assert delete_response.status_code == 404


def test_scenario_routes_return_404_for_missing_entities(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    list_response = client.get(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 404

    create_response = client.post(
        f"/api/v2/{tenant}/scenarios",
        params={"problem_id": problem_id},
        headers={"Session-ID": "session-404"},
        json={"base_scenario_id": "missing-scenario"},
    )
    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Scenario 'missing-scenario' not found for problem 'default'"
    }

    read_response = client.get(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404

    update_response = client.put(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
        headers={"Version": "1"},
        json={"name": "Updated"},
    )
    assert update_response.status_code == 404

    save_response = client.post(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
        headers={"Session-ID": "session-404", "Version": "1"},
        json={"name": "Save failed"},
    )
    assert save_response.status_code == 404

    delete_response = client.delete(
        f"/api/v2/{tenant}/scenarios/missing-scenario",
        params={"problem_id": problem_id},
        headers={"Version": "1"},
    )
    assert delete_response.status_code == 404


def test_session_routes_return_404_for_missing_problem_or_session(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": "missing-problem"},
        json={"metadata": {}},
    )
    assert create_response.status_code == 404

    list_response = client.get(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": "missing-problem"},
    )
    assert list_response.status_code == 404

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/missing-session",
        params={"problem_id": problem_id},
    )
    assert read_response.status_code == 404
    assert read_response.json() == {
        "detail": "Session 'missing-session' not found for problem 'default'"
    }

    delete_response = client.delete(
        f"/api/v2/{tenant}/sessions/missing-session",
        params={"problem_id": problem_id},
    )
    assert delete_response.status_code == 404


def test_evaluation_routes_return_404_for_missing_entities(
    client,
    tenant: str,
    problem_id: str,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": "missing-scenario"},
    )
    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Scenario 'missing-scenario' not found for problem 'default'"
    }

    read_response = client.get(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id, "scenario_id": "missing-scenario"},
    )
    assert read_response.status_code == 404
    assert read_response.json() == {
        "detail": "Evaluation for scenario 'missing-scenario' not found for problem 'default'"
    }

    data_response = client.get(
        f"/api/v2/{tenant}/evaluations/data",
        params={"problem_id": problem_id, "scenario_id": "missing-scenario"},
    )
    assert data_response.status_code == 404

    session_response = client.post(
        f"/api/v2/{tenant}/evaluations",
        params={"problem_id": problem_id},
        headers={"Session-ID": "missing-session"},
        json={"scenario_id": "missing-scenario"},
    )
    assert session_response.status_code == 404


def test_data_and_widget_routes_return_500_for_failing_collaborators(
    client,
    error_client,
    handler,
    tenant: str,
) -> None:
    handler.data_loader = None
    no_loader_response = error_client.get(
        f"/api/v2/{tenant}/data/overtourism/indexes/categories"
    )
    assert no_loader_response.status_code == 500

    class BrokenLoader:
        get_categories = staticmethod(_raise_runtime_error)
        get_list = staticmethod(_raise_runtime_error)
        get_dataframe = staticmethod(_raise_runtime_error)
        get_map = staticmethod(_raise_runtime_error)

    handler.data_loader = BrokenLoader()
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/categories"
        ).status_code
        == 500
    )
    assert (
        error_client.get(f"/api/v2/{tenant}/data/overtourism/indexes/list").status_code
        == 500
    )
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/data",
            params={"dataframe": "presence"},
        ).status_code
        == 500
    )
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/map",
            params={"map": "districts"},
        ).status_code
        == 500
    )

    handler.viewer = None
    empty_widget_response = client.get(f"/api/v2/{tenant}/widgets")
    assert empty_widget_response.status_code == 200
    assert empty_widget_response.json() == {"widgets": {}}

    class BrokenViewer:
        @staticmethod
        def get_widgets(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

    handler.viewer = BrokenViewer()
    widget_response = error_client.get(f"/api/v2/{tenant}/widgets")
    assert widget_response.status_code == 500
