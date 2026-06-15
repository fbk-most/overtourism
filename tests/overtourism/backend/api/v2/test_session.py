# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.session import manager as session_manager_module


def test_session_routes_manage_the_full_session_lifecycle(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_manager_module,
        "uuid4",
        lambda: SimpleNamespace(hex="session-fixed"),
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={},
        json={"metadata": {"source": "ui"}},
    )

    assert create_response.status_code == 200
    assert create_response.json()["session_id"] == "session-fixed"
    assert create_response.json()["metadata"] == {"source": "ui"}
    assert create_response.json()["draft_ids"] == []

    list_response = client.get(
        f"/api/v2/{tenant}/sessions",
        params={},
    )

    assert list_response.status_code == 200
    assert [item["session_id"] for item in list_response.json()] == ["session-fixed"]

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/session-fixed",
        params={},
    )

    assert read_response.status_code == 200
    assert read_response.json()["drafts"] == []
    assert read_response.json()["evaluations"] == {}

    delete_response = client.delete(
        f"/api/v2/{tenant}/sessions/session-fixed",
        params={},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Session deleted successfully"}
    assert manager.session_manager.list_sessions() == []


def test_session_detail_embeds_evaluation_metadata_without_result(
    client,
    tenant: str,
    problem_id: str,
    scenario_id: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_manager_module,
        "uuid4",
        lambda: SimpleNamespace(hex="session-detail"),
    )

    create_session_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {"source": "ui"}},
    )
    assert create_session_response.status_code == 200

    draft_response = client.post(
        f"/api/v2/{tenant}/sessions/session-detail/scenarios",
        params={"problem_id": problem_id},
        json={
            "base_scenario_id": scenario_id,
            "values": {"visits": 5},
            "name": "Session draft",
        },
    )
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["scenario_id"]

    evaluation_response = client.post(
        f"/api/v2/{tenant}/sessions/session-detail/evaluations",
        params={"problem_id": problem_id},
        json={"scenario_id": draft_id, "ensemble_size": 4},
    )
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()

    response = client.get(
        f"/api/v2/{tenant}/sessions/session-detail",
        params={"problem_id": problem_id},
    )

    assert response.status_code == 200
    assert response.json()["evaluations"] == {
        draft_id: {
            "evaluation_id": evaluation["evaluation_id"],
            "scenario_id": draft_id,
            "type": "default",
            "version": 2,
            "state": "COMPLETED",
            "started": evaluation["started"],
            "finished": evaluation["finished"],
        }
    }
