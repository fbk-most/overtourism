# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from fastapi import HTTPException
from overtourism.backend.api.shared.exceptions import ProblemNotFound
from overtourism.backend.api.v2.models.problem import PostProblemData, UpdateProblemData
from overtourism.backend.api.v2.utils import (
    api_entity_payload,
    arrange_data,
    build_problem_extras,
    check_version,
    evaluation_manager,
    evaluation_result_to_dict,
    get_evaluation_or_404,
    get_problem_editable_indexes,
    get_problem_or_404,
    get_proposal_or_404,
    get_scenario_or_404,
    get_session_evaluation_or_404,
    get_session_or_404,
    get_session_scenario_or_404,
    get_widget_by_group,
    get_widgets,
    model_values,
    parse_version,
    prepare_values,
    problem_from_model,
    problem_manager,
    problem_update_from_model,
    proposal_manager,
    scenario_index_diffs,
    scenario_manager,
    session_summary_to_api,
    session_to_api,
    slugify_name,
)
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.manager import Manager


class SnapshotResult:
    def __init__(self, payload):
        self.payload = payload

    def to_snapshot(self):
        return self.payload


def test_problem_helpers_build_expected_payloads(handler) -> None:
    extras = build_problem_extras(handler, {"groups": ["pressure"]})
    assert extras == {"editable_indexes": ["pressure-widget"]}

    create_model = PostProblemData(
        problem_name="Lake Cleanup",
        problem_description="Reduce pressure",
        extras={"ignored": True},
    )
    assert problem_from_model(handler, create_model) == {
        "name": "Lake Cleanup",
        "description": "Reduce pressure",
        "extras": {"editable_indexes": []},
    }

    update_model = UpdateProblemData(
        problem_name="Updated",
        problem_description="Updated description",
    )
    assert problem_update_from_model(handler, update_model) == {
        "name": "Updated",
        "description": "Updated description",
        "extras": {"editable_indexes": []},
    }

    assert get_problem_editable_indexes({"editable_indexes": [1, "two"]}) == [
        "1",
        "two",
    ]
    assert slugify_name("Lake Cleanup 2026!") == "lake-cleanup-2026"


def test_optional_viewer_and_data_hooks_are_respected(
    handler,
    manager: Manager,
    problem_id: str,
) -> None:
    assert get_widgets(handler, {"visits": 3}, language="en") == {
        "summary": {
            "language": "en",
            "values": {"visits": 3},
        }
    }
    assert get_widget_by_group(handler, ["pressure"]) == ["pressure-widget"]
    assert prepare_values(handler, {"visits": 2}) == {"visits": 2}
    assert arrange_data(handler, SnapshotResult({"score": 1})) == {"score": 1}
    assert arrange_data(
        handler,
        SnapshotResult({"score": 1, "detail": 2}),
        params=["detail"],
    ) == {"detail": 2}

    bare_handler = Handler(manager=manager)
    payload = {"visits": 5}
    assert get_widgets(bare_handler, payload) is None
    assert get_widget_by_group(bare_handler, ["pressure"]) == []
    assert prepare_values(bare_handler, payload) is payload
    assert arrange_data(bare_handler, payload) is payload

    assert problem_manager(handler, problem_id) is manager.problem_manager
    assert (
        proposal_manager(handler, problem_id) is manager.proposal_managers[problem_id]
    )
    assert (
        scenario_manager(handler, problem_id) is manager.scenario_managers[problem_id]
    )
    assert (
        evaluation_manager(handler, problem_id)
        is manager.evaluation_managers[problem_id]
    )

    assert evaluation_result_to_dict(None) == {}
    assert evaluation_result_to_dict({"score": 2}) == {"score": 2}
    assert evaluation_result_to_dict(SnapshotResult({"score": 3})) == {"score": 3}


def test_not_found_helpers_translate_backend_errors_to_http_exceptions(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    assert get_problem_or_404(handler, tenant, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id: (_ for _ in ()).throw(
        FileNotFoundError(problem_id)
    )
    with pytest.raises(ProblemNotFound):
        get_problem_or_404(handler, tenant, "missing-problem")


def test_session_and_entity_helpers_return_domain_objects_or_404(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    assert get_problem_or_404(handler, tenant, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id: manager.problem_manager.read_problem(
        problem_id
    )
    with pytest.raises(ProblemNotFound):
        get_problem_or_404(handler, "wrong-tenant", problem_id)

    assert get_scenario_or_404(handler, problem_id, "default").scenario_id == "default"
    assert (
        get_proposal_or_404(handler, problem_id, proposal_id).proposal_id == proposal_id
    )
    assert (
        get_evaluation_or_404(handler, problem_id, "default").scenario_id == "default"
    )

    with pytest.raises(HTTPException) as scenario_exc:
        get_scenario_or_404(handler, problem_id, "missing-scenario")
    assert scenario_exc.value.status_code == 404

    with pytest.raises(HTTPException) as proposal_exc:
        get_proposal_or_404(handler, problem_id, "missing-proposal")
    assert proposal_exc.value.status_code == 404

    with pytest.raises(HTTPException) as evaluation_exc:
        get_evaluation_or_404(handler, problem_id, "missing-scenario")
    assert evaluation_exc.value.status_code == 404

    session = manager.create_session(
        problem_id, "session-utils", metadata={"source": "ui"}
    )
    draft = manager.create_session_scenario(
        problem_id,
        "session-utils",
        "default",
        values={"visits": 8},
        name="Draft",
    )
    evaluation = manager.create_session_evaluation(
        problem_id,
        "session-utils",
        draft.scenario_id,
        ensemble_size=4,
    )

    summary = session_summary_to_api(session)
    assert summary.session_id == "session-utils"
    assert summary.metadata == {"source": "ui"}

    session_payload = session_to_api(session)
    assert session_payload.draft_ids == [draft.scenario_id]
    assert [item.scenario_id for item in session_payload.drafts] == [draft.scenario_id]
    assert session_payload.drafts[0].version == 1
    assert (
        session_payload.evaluations[draft.scenario_id].evaluation_id
        == evaluation.evaluation_id
    )
    assert session_payload.evaluations[draft.scenario_id].version == 2

    assert (
        get_session_or_404(handler, problem_id, "session-utils").session_id
        == "session-utils"
    )
    assert (
        get_session_scenario_or_404(
            handler,
            problem_id,
            "session-utils",
            draft.scenario_id,
        ).scenario_id
        == draft.scenario_id
    )
    assert (
        get_session_evaluation_or_404(
            handler,
            problem_id,
            "session-utils",
            draft.scenario_id,
        ).evaluation_id
        == evaluation.evaluation_id
    )

    with pytest.raises(HTTPException) as session_exc:
        get_session_or_404(handler, problem_id, "missing-session")
    assert session_exc.value.status_code == 404

    with pytest.raises(HTTPException) as draft_exc:
        get_session_scenario_or_404(
            handler,
            problem_id,
            "session-utils",
            "missing-scenario",
        )
    assert draft_exc.value.status_code == 404

    with pytest.raises(HTTPException) as eval_exc:
        get_session_evaluation_or_404(
            handler,
            problem_id,
            "session-utils",
            "missing-scenario",
        )
    assert eval_exc.value.status_code == 404


def test_version_and_cdt_helpers_cover_validation_and_model_bridges(
    handler,
    manager: Manager,
    problem_id: str,
    monkeypatch,
) -> None:
    assert api_entity_payload({"problem_id": problem_id, "version": 7}) == {
        "problem_id": problem_id,
        "version": 7,
    }

    assert parse_version(None) is None
    assert parse_version(3) == 3
    assert parse_version("3") == 3

    with pytest.raises(HTTPException) as non_integer_exc:
        parse_version("abc")
    assert non_integer_exc.value.status_code == 400
    assert non_integer_exc.value.detail == "version must contain an integer value"

    with pytest.raises(HTTPException) as non_positive_exc:
        parse_version("0")
    assert non_positive_exc.value.status_code == 400
    assert non_positive_exc.value.detail == "version must be a positive integer"

    check_version(3, 3)

    with pytest.raises(HTTPException) as missing_exc:
        check_version(3, None)
    assert missing_exc.value.status_code == 428
    assert missing_exc.value.detail == "Missing version in entity payload"

    with pytest.raises(HTTPException) as mismatch_exc:
        check_version(3, "2")
    assert mismatch_exc.value.status_code == 412
    assert (
        mismatch_exc.value.detail
        == "version mismatch: expected 2, current version is 3"
    )

    fake_module = ModuleType("scenario")

    class FakeCDTScenario:
        def __init__(self, model, overrides=None):
            self.model = model
            self.overrides = overrides

    fake_module.Scenario = FakeCDTScenario
    monkeypatch.setitem(
        sys.modules,
        "civic_digital_twins.dt_model.simulation.scenario",
        fake_module,
    )

    manager.update_scenario(problem_id, "default", values={"visits": 9})
    scenario = manager.read_scenario(problem_id, "default")

    monkeypatch.setattr(
        handler.manager.model_evaluator,
        "_values_to_overrides",
        lambda model, values: {"visits": values["visits"]},
    )
    monkeypatch.setattr(
        handler.manager.model_evaluator,
        "get_index_diffs",
        lambda cdt_scenario: {"visits": f"+{cdt_scenario.overrides['visits']}"},
    )
    monkeypatch.setattr(
        handler.manager.model_evaluator,
        "get_model_values",
        lambda cdt_scenario: {"model": cdt_scenario.model.name},
    )

    assert scenario_index_diffs(handler, scenario) == {"visits": "+9"}
    assert model_values(handler) == {"model": "fake-model"}
