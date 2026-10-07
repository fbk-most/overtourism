# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
import requests
from fastapi import HTTPException

from overtourism.backend.api.utils import executor_utils
from overtourism.backend.api.utils.utils import (
    get_evaluation_or_404,
    get_problem_or_404,
    get_proposal_or_404,
    get_scenario_or_404,
    get_session_evaluation_by_id_or_404,
    get_session_evaluation_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    scenario_index_diffs,
)
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.utils.exception import EntityDoesNotExist


class SnapshotResult:
    def __init__(self, payload):
        self.payload = payload

    def to_snapshot(self):
        return self.payload


def test_session_helpers_do_not_mask_internal_errors(handler) -> None:
    def raise_internal_error(*args, **kwargs):
        raise RuntimeError("internal failure")

    handler.manager.read_session = raise_internal_error
    handler.manager.read_session_scenario = raise_internal_error
    handler.manager.read_session_evaluation = raise_internal_error
    handler.manager.read_session_evaluation_by_id = raise_internal_error

    with pytest.raises(RuntimeError, match="internal failure"):
        get_session_or_404(handler, "session")
    with pytest.raises(RuntimeError, match="internal failure"):
        get_session_scenario_or_404(handler, "session", "scenario")
    with pytest.raises(RuntimeError, match="internal failure"):
        get_session_evaluation_or_404(handler, "session", "scenario")
    with pytest.raises(RuntimeError, match="internal failure"):
        get_session_evaluation_by_id_or_404(handler, "session", "evaluation")


def test_scenario_index_diffs_batches_scenarios_by_territory(
    manager: Manager,
    territory: str,
    monkeypatch,
) -> None:
    first_scenario = manager.scenario_manager.create_scenario(
        "scenario-diff-first",
        territory,
        param_overrides={"season": "peak"},
    )
    second_scenario = manager.scenario_manager.create_scenario(
        "scenario-diff-second",
        territory,
        param_overrides={"car mode share": 0.8},
    )
    unchanged_scenario = manager.scenario_manager.create_scenario(
        "scenario-diff-unchanged",
        territory,
    )
    calls: list[tuple[str, dict[str, dict[str, object]]]] = []

    def fake_call_index_diffs(
        requested_territory: str,
        overrides_by_scenario: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, str]]:
        calls.append((requested_territory, overrides_by_scenario))
        return {
            "scenario-diff-first": {"season": "base -> peak"},
            "scenario-diff-second": {"car mode share": "0.69 -> 0.8"},
        }

    monkeypatch.setattr(
        "overtourism.backend.api.utils.utils.call_index_diffs",
        fake_call_index_diffs,
    )

    assert scenario_index_diffs(
        [first_scenario, second_scenario, unchanged_scenario]
    ) == {
        "scenario-diff-first": {"season": "base -> peak"},
        "scenario-diff-second": {"car mode share": "0.69 -> 0.8"},
    }
    assert calls == [
        (
            territory,
            {
                "scenario-diff-first": {"season": "peak"},
                "scenario-diff-second": {"car mode share": 0.8},
            },
        ),
    ]


def test_scenario_index_diffs_returns_empty_when_layer_3_is_unavailable(
    manager: Manager,
    territory: str,
    monkeypatch,
) -> None:
    scenario = manager.scenario_manager.create_scenario(
        "scenario-diff-unavailable",
        territory,
        param_overrides={"season": "peak"},
    )

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("Layer 3 unavailable")

    monkeypatch.setattr(
        "overtourism.backend.api.utils.utils.call_index_diffs",
        raise_connection_error,
    )

    assert scenario_index_diffs([scenario]) == {}


def test_call_index_diffs_posts_batched_overrides(monkeypatch) -> None:
    expected_diffs = {"scenario-1": {"season": "base -> peak"}}
    captured_request = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, dict[str, dict[str, str]]]:
            return {"index_diffs_by_scenario": expected_diffs}

    def fake_post(url: str, *, json: dict[str, dict[str, dict[str, int | str]]]):
        captured_request["url"] = url
        captured_request["json"] = json
        return FakeResponse()

    monkeypatch.setattr(executor_utils, "model_backend_url", "http://model.test")
    monkeypatch.setattr(executor_utils.requests, "post", fake_post)

    actual_diffs = executor_utils.call_index_diffs(
        "molveno",
        {"scenario-1": {"season": "peak"}},
    )

    assert captured_request == {
        "url": "http://model.test/models/molveno/index-diffs",
        "json": {
            "param_overrides_by_scenario": {"scenario-1": {"season": "peak"}}
        },
    }
    assert actual_diffs == expected_diffs


def test_not_found_helpers_translate_backend_errors_to_http_exceptions(
    handler,
    manager: Manager,
    territory: str,
    problem_id: str,
) -> None:
    assert get_problem_or_404(territory, handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id, territory=None: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(territory, handler, "missing-problem")
    assert exc_info.value.status_code == 404


def test_session_and_entity_helpers_return_domain_objects_or_404(
    handler,
    manager: Manager,
    territory: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    base_scenario_id = f"{territory}_base_scenario"

    assert get_problem_or_404(territory, handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id, territory=None: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(territory, handler, problem_id)
    assert exc_info.value.status_code == 404

    assert (
        get_scenario_or_404(territory, handler, base_scenario_id).scenario_id
        == base_scenario_id
    )
    assert (
        get_proposal_or_404(territory, handler, proposal_id).proposal_id == proposal_id
    )
    evaluation = handler.manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        base_scenario_id,
    )
    scenario = handler.manager.read_scenario(base_scenario_id)
    evaluation = handler.execution_manager_registry.get(territory).execute_evaluation(
        evaluation,
        scenario,
    )
    handler.manager.evaluation_manager.save_evaluation(evaluation)
    assert (
        get_evaluation_or_404(territory, handler, evaluation.evaluation_id).scenario_id
        == base_scenario_id
    )

    with pytest.raises(HTTPException) as scenario_exc:
        get_scenario_or_404(territory, handler, "missing-scenario")
    assert scenario_exc.value.status_code == 404

    with pytest.raises(HTTPException) as proposal_exc:
        get_proposal_or_404(territory, handler, "missing-proposal")
    assert proposal_exc.value.status_code == 404

    with pytest.raises(HTTPException) as evaluation_exc:
        get_evaluation_or_404(territory, handler, "missing-scenario")
    assert evaluation_exc.value.status_code == 404

    session = manager.session_manager.create_session(metadata={"source": "ui"})
    draft = manager.create_session_scenario(
        session.session_id,
        base_scenario_id,
        param_overrides={"visits": 8},
    )
    evaluation = handler.execution_manager_registry.get(territory).execute_evaluation(
        manager.evaluation_manager.build_running_evaluation(
            "session-evaluation",
            scenario_id=draft.scenario_id,
        ),
        draft,
        ensemble_size=4,
    )
    manager.create_session_evaluation(session.session_id, draft.scenario_id, evaluation)

    assert (
        get_session_or_404(handler, session.session_id).session_id == session.session_id
    )
    assert (
        get_session_scenario_or_404(
            handler,
            session.session_id,
            draft.scenario_id,
        ).scenario_id
        == draft.scenario_id
    )
    assert (
        get_session_evaluation_or_404(
            handler,
            session.session_id,
            draft.scenario_id,
        ).evaluation_id
        == evaluation.evaluation_id
    )

    with pytest.raises(HTTPException) as session_exc:
        get_session_or_404(handler, "missing-session")
    assert session_exc.value.status_code == 404

    with pytest.raises(HTTPException) as draft_exc:
        get_session_scenario_or_404(
            handler,
            session.session_id,
            "missing-scenario",
        )
    assert draft_exc.value.status_code == 404

    with pytest.raises(HTTPException) as eval_exc:
        get_session_evaluation_or_404(
            handler,
            session.session_id,
            "missing-scenario",
        )
    assert eval_exc.value.status_code == 404
