# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.scenario import scenario as scenario_module
from overtourism.dt_manager.scenario.scenario import Scenario

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_create_default_uses_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(scenario_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    scenario = Scenario.create_default("scenario-alpha", "tenant-alpha")

    assert scenario.to_dict() == {
        "scenario_id": "scenario-alpha",
        "tenant": "tenant-alpha",
        "session_id": None,
        "version": 1,
        "name": "scenario-alpha",
        "description": "scenario-alpha scenario",
        "created": FIXED_TIMESTAMP,
        "updated": FIXED_TIMESTAMP,
        "extras": {},
        "param_overrides": {},
    }


def test_from_dict_round_trip_with_param_overrides() -> None:
    payload = {
        "scenario_id": "scenario-alpha",
        "tenant": "tenant-alpha",
        "session_id": "session-1",
        "version": 1,
        "name": "Scenario Alpha",
        "description": "Primary scenario",
        "created": "2026-05-15T10:00:00Z",
        "updated": "2026-05-15T11:00:00Z",
        "extras": {"kind": "scenario"},
        "param_overrides": {"visits": 12.5, "population": 7},
    }

    scenario = Scenario.from_dict(payload)

    assert scenario.session_id == "session-1"
    assert scenario.param_overrides == payload["param_overrides"]
    assert scenario.to_dict() == payload


def test_from_dict_fills_missing_timestamps(monkeypatch) -> None:
    monkeypatch.setattr(scenario_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    scenario = Scenario.from_dict(
        {
            "scenario_id": "scenario-beta",
            "tenant": "tenant-beta",
            "version": 1,
            "name": "Scenario Beta",
            "description": "Secondary scenario",
            "extras": {},
            "param_overrides": {},
        }
    )

    assert scenario.tenant == "tenant-beta"
    assert scenario.created == FIXED_TIMESTAMP
    assert scenario.updated == FIXED_TIMESTAMP
    assert scenario.param_overrides == {}
