# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
    EvaluationState,
)

from overtourism.dt_manager.evaluation import evaluation as evaluation_module

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_create_default_uses_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(evaluation_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    evaluation = Evaluation.create_default(
        "evaluation-alpha",
        scenario_id="scenario-alpha",
        type=DEFAULT_EVALUATION_TYPE,
    )

    assert evaluation.to_dict() == {
        "evaluation_id": "evaluation-alpha",
        "scenario_id": "scenario-alpha",
        "type": DEFAULT_EVALUATION_TYPE,
        "state": EvaluationState.RUNNING.value,
        "started": FIXED_TIMESTAMP,
        "finished": None,
        "result": None,
    }


def test_from_dict_converts_state_and_round_trips() -> None:
    payload = {
        "evaluation_id": "evaluation-alpha",
        "scenario_id": "scenario-alpha",
        "type": DEFAULT_EVALUATION_TYPE,
        "state": EvaluationState.COMPLETED.value,
        "started": "2026-05-15T10:00:00Z",
        "finished": "2026-05-15T11:00:00Z",
        "result": {"score": 0.91, "notes": ["ok"]},
    }

    evaluation = Evaluation.from_dict(payload)

    assert evaluation.state is EvaluationState.COMPLETED
    assert evaluation.to_dict() == payload


def test_from_dict_defaults_state_to_running() -> None:
    evaluation = Evaluation.from_dict(
        {
            "evaluation_id": "evaluation-beta",
            "scenario_id": "scenario-beta",
            "type": DEFAULT_EVALUATION_TYPE,
        }
    )

    assert evaluation.state is EvaluationState.RUNNING
    assert evaluation.started is None
    assert evaluation.finished is None
    assert evaluation.result is None
