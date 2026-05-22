# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.problem import problem as problem_module
from overtourism.dt_manager.problem.problem import Problem

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_create_default_uses_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(problem_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    problem = Problem.create_default("problem-alpha")

    assert problem.to_dict() == {
        "problem_id": "problem-alpha",
        "version": 1,
        "tenant": "default",
        "name": "problem-alpha",
        "description": "problem-alpha problem",
        "created": FIXED_TIMESTAMP,
        "updated": FIXED_TIMESTAMP,
        "extras": {},
    }


def test_from_dict_round_trip() -> None:
    payload = {
        "problem_id": "problem-alpha",
        "version": 1,
        "tenant": "molveno",
        "name": "Problem Alpha",
        "description": "Primary problem",
        "created": "2026-05-15T10:00:00Z",
        "updated": "2026-05-15T11:00:00Z",
        "extras": {"region": "tn"},
    }

    problem = Problem.from_dict(payload)

    assert problem.to_dict() == payload
