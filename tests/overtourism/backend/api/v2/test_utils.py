# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from fastapi import HTTPException

from overtourism.backend.api.utils.utils import (
    get_evaluation_or_404,
    get_problem_or_404,
    get_proposal_or_404,
    get_scenario_or_404,
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


def test_scenario_index_diffs_uses_the_layer_3_schema(
    handler,
    manager: Manager,
    tenant: str,
    monkeypatch,
) -> None:
    scenario = manager.scenario_manager.create_scenario(
        "scenario-diff",
        tenant,
        param_overrides={
            "season": "peak",
            "parking capacity": [120.0, 240.0],
            "car mode share": 0.8,
        },
    )
    schema_calls: list[str] = []
    monkeypatch.setattr(
        "overtourism.backend.api.utils.utils.call_schema",
        lambda requested_tenant: (
            schema_calls.append(requested_tenant)
            or {
                "indexes": [
                    {
                        "name": "season",
                        "kind": "categorical",
                        "default_category": "base",
                    },
                    {
                        "name": "parking capacity",
                        "kind": "distribution",
                        "default_range": [100.0, 200.0],
                    },
                    {"name": "car mode share", "kind": "scalar", "default": 0.69},
                ]
            }
        ),
    )

    assert scenario_index_diffs(handler, scenario) == {
        "season": "base -> peak",
        "parking capacity": "100-200 -> 120-240",
        "car mode share": "0.69 -> 0.8",
    }
    assert schema_calls == [tenant]


def test_not_found_helpers_translate_backend_errors_to_http_exceptions(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
) -> None:
    assert get_problem_or_404(tenant, handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id, tenant=None: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(tenant, handler, "missing-problem")
    assert exc_info.value.status_code == 404


def test_session_and_entity_helpers_return_domain_objects_or_404(
    handler,
    manager: Manager,
    tenant: str,
    problem_id: str,
    proposal_id: str,
) -> None:
    base_scenario_id = f"{tenant}_base_scenario"

    assert get_problem_or_404(tenant, handler, problem_id).problem_id == problem_id

    manager.read_problem = lambda problem_id, tenant=None: (_ for _ in ()).throw(
        EntityDoesNotExist(problem_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        get_problem_or_404(tenant, handler, problem_id)
    assert exc_info.value.status_code == 404

    assert (
        get_scenario_or_404(tenant, handler, base_scenario_id).scenario_id
        == base_scenario_id
    )
    assert get_proposal_or_404(tenant, handler, proposal_id).proposal_id == proposal_id
    evaluation = handler.manager.evaluation_manager.create_evaluation(
        "evaluation-alpha",
        base_scenario_id,
    )
    scenario = handler.manager.read_scenario(base_scenario_id)
    evaluation = handler.execution_manager_registry.get(tenant).execute_evaluation(
        evaluation,
        scenario,
    )
    handler.manager.evaluation_manager.save_evaluation(evaluation)
    assert (
        get_evaluation_or_404(tenant, handler, evaluation.evaluation_id).scenario_id
        == base_scenario_id
    )

    with pytest.raises(HTTPException) as scenario_exc:
        get_scenario_or_404(tenant, handler, "missing-scenario")
    assert scenario_exc.value.status_code == 404

    with pytest.raises(EntityDoesNotExist):
        get_proposal_or_404(tenant, handler, "missing-proposal")

    with pytest.raises(EntityDoesNotExist):
        get_evaluation_or_404(tenant, handler, "missing-scenario")

    session = manager.session_manager.create_session(metadata={"source": "ui"})
    draft = manager.create_session_scenario(
        session.session_id,
        base_scenario_id,
        param_overrides={"visits": 8},
    )
    evaluation = handler.execution_manager_registry.get(tenant).execute_evaluation(
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
