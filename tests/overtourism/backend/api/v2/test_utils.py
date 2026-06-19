# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from fastapi import HTTPException

from overtourism.backend.api.v2.utils import (
    arrange_data,
    check_version,
    get_evaluation_or_404,
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
    scenario_index_diffs,
)
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.utils.exception import EntityDoesNotExist


class SnapshotResult:
    def __init__(self, payload):
        self.payload = payload

    def to_snapshot(self):
        return self.payload


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


def test_not_found_helpers_translate_backend_errors_to_http_exceptions(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    assert get_problem_or_404(handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(handler, "missing-problem")
    assert exc_info.value.status_code == 404


def test_session_and_entity_helpers_return_domain_objects_or_404(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"

    assert get_problem_or_404(handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(handler, problem_id)
    assert exc_info.value.status_code == 404

    assert (
        get_scenario_or_404(handler, base_scenario_id).scenario_id == base_scenario_id
    )
    assert get_proposal_or_404(handler, proposal_id).proposal_id == proposal_id
    evaluation = manager.evaluate_scenario(base_scenario_id)
    assert (
        get_evaluation_or_404(handler, evaluation.evaluation_id).scenario_id
        == base_scenario_id
    )

    with pytest.raises(HTTPException) as scenario_exc:
        get_scenario_or_404(handler, "missing-scenario")
    assert scenario_exc.value.status_code == 404

    with pytest.raises(EntityDoesNotExist):
        get_proposal_or_404(handler, "missing-proposal")

    with pytest.raises(EntityDoesNotExist):
        get_evaluation_or_404(handler, "missing-scenario")

    session = manager.session_manager.create_session(metadata={"source": "ui"})
    draft = manager.create_session_scenario(
        session.session_id,
        base_scenario_id,
        values={"visits": 8},
    )
    evaluation = manager.create_session_evaluation(
        session.session_id,
        draft.scenario_id,
        ensemble_size=4,
    )

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


def test_version_and_cdt_helpers_cover_validation_and_model_bridges(
    handler,
    manager: Manager,
    problem_id: str,
    monkeypatch,
) -> None:
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

    scenario = manager.read_scenario(
        f"{handler.manager.base_problem_config.tenant}_base_scenario"
    )
    manager.update_scenario(scenario.scenario_id, values={"visits": 9})
    scenario = manager.read_scenario(scenario.scenario_id)

    monkeypatch.setattr(
        handler.manager.scenario_manager.model_evaluator,
        "_values_to_overrides",
        lambda model, values: {"visits": values["visits"]},
    )
    monkeypatch.setattr(
        handler.manager.scenario_manager.model_evaluator,
        "get_index_diffs",
        lambda cdt_scenario: {"visits": f"+{cdt_scenario.overrides['visits']}"},
    )
    monkeypatch.setattr(
        handler.manager.scenario_manager.model_evaluator,
        "get_model_values",
        lambda cdt_scenario: {"model": cdt_scenario.model.name},
    )

    assert scenario_index_diffs(handler, scenario) == {"visits": "+9"}
    assert model_values(handler) == {"model": "fake-model"}
