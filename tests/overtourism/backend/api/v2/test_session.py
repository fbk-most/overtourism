# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

from overtourism.backend.api.v2 import session as session_api
from overtourism.dt_manager.manager.manager import Manager


def test_session_routes_manage_the_full_session_lifecycle(
    client,
    manager: Manager,
    tenant: str,
    problem_id: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_api,
        "uuid4",
        lambda: SimpleNamespace(hex="session-fixed"),
    )

    create_response = client.post(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
        json={"metadata": {"source": "ui"}},
    )

    assert create_response.status_code == 200
    assert create_response.json()["session_id"] == "session-fixed"
    assert create_response.json()["metadata"] == {"source": "ui"}
    assert create_response.json()["draft_ids"] == []

    list_response = client.get(
        f"/api/v2/{tenant}/sessions",
        params={"problem_id": problem_id},
    )

    assert list_response.status_code == 200
    assert [item["session_id"] for item in list_response.json()] == ["session-fixed"]

    read_response = client.get(
        f"/api/v2/{tenant}/sessions/session-fixed",
        params={"problem_id": problem_id},
    )

    assert read_response.status_code == 200
    assert read_response.json()["drafts"] == []
    assert read_response.json()["evaluations"] == {}

    delete_response = client.delete(
        f"/api/v2/{tenant}/sessions/session-fixed",
        params={"problem_id": problem_id},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Session deleted successfully"}
    assert manager.session_manager.list_sessions(problem_id) == []
