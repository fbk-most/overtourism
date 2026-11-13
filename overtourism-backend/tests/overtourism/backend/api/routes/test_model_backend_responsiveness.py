# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from overtourism.backend.auth.identity.users import UserRole
from overtourism.backend.auth.tokens.context import AuthContext
from overtourism.backend.auth.tokens.dependencies import get_auth_context
from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings
from overtourism.backend.main import create_app
from overtourism.backend.utils import executor_utils


def test_slow_model_evaluation_does_not_block_auth_me(
    handler,
    territory: str,
    scenario_id: str,
    monkeypatch,
) -> None:
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        territory=territory,
        subject=None,
        token=None,
        claims={},
    )

    class ModelResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"result": "ok"}

    model_requests: list[str] = []
    model_request_started = threading.Event()
    release_model_request = threading.Event()

    def slow_model_request(url: str, **kwargs) -> ModelResponse:
        model_requests.append(url)
        model_request_started.set()
        if not release_model_request.wait(timeout=5):
            raise TimeoutError("test did not release the Model API request")
        return ModelResponse()

    monkeypatch.setattr(executor_utils.requests, "post", slow_model_request)

    with TestClient(app) as client:
        session_response = client.post(
            f"/api/{territory}/sessions",
            json={"metadata": {}},
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]

        draft_response = client.post(
            f"/api/{territory}/sessions/{session_id}/scenarios",
            json={"base_scenario_id": scenario_id, "summary": "slow model"},
        )
        assert draft_response.status_code == 200
        draft_id = draft_response.json()["scenario_id"]

        with ThreadPoolExecutor(max_workers=2) as executor:
            evaluation_future = executor.submit(
                client.post,
                f"/api/{territory}/sessions/{session_id}/evaluations",
                json={"scenario_id": draft_id},
            )
            assert model_request_started.wait(timeout=1)

            auth_future = executor.submit(client.get, "/api/auth/me")
            try:
                auth_future.result(timeout=1)
                auth_responsive = True
            except FutureTimeoutError:
                auth_responsive = False
            finally:
                release_model_request.set()

            evaluation_response = evaluation_future.result(timeout=2)
            auth_response = auth_future.result(timeout=2)

    assert auth_response.status_code == 200
    assert evaluation_response.status_code == 200
    assert len(model_requests) == 1
    assert auth_responsive


@pytest.mark.parametrize(
    "request_path",
    ["/api/default/territories", "/api/auth/me"],
)
def test_slow_model_registry_does_not_block_other_routes(
    handler,
    territory: str,
    request_path: str,
    monkeypatch,
) -> None:
    app = create_app(handler)
    if request_path == "/api/auth/me":
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            authenticated=True,
            territory=territory,
            subject="admin-sub",
            token="admin-token",
            claims={},
        )
        monkeypatch.setattr(
            "overtourism.backend.auth.api.router.resolve_current_user",
            lambda *args: SimpleNamespace(
                user_id="admin-id",
                identifier="admin@example.org",
                role=UserRole.ADMIN,
                territories=set(),
            ),
        )
    else:
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            authenticated=False,
            territory=territory,
            subject=None,
            token=None,
            claims={},
        )
    app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(enabled=False)

    model_requests: list[str] = []
    model_request_started = threading.Event()
    release_model_request = threading.Event()

    class ModelResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> list[dict[str, str]]:
            return [{"key": territory}]

    def slow_model_request(url: str, **kwargs) -> ModelResponse:
        model_requests.append(url)
        model_request_started.set()
        if not release_model_request.wait(timeout=5):
            raise TimeoutError("test did not release the Model API request")
        return ModelResponse()

    monkeypatch.setattr(executor_utils.requests, "get", slow_model_request)

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as executor:
        model_future = executor.submit(client.get, request_path)
        assert model_request_started.wait(timeout=1)

        health_future = executor.submit(client.get, "/health/live")
        try:
            health_future.result(timeout=1)
            health_responsive = True
        except FutureTimeoutError:
            health_responsive = False
        finally:
            release_model_request.set()

        model_response = model_future.result(timeout=2)
        health_response = health_future.result(timeout=2)

    assert model_response.status_code == 200
    assert health_response.status_code == 200
    assert len(model_requests) == 1
    assert health_responsive
