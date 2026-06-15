# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.indexes.index import IndexEntry, IndexType
from overtourism.dt_manager.scenario import scenario as scenario_module
from overtourism.dt_manager.scenario.scenario import Scenario

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_create_default_uses_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(scenario_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    scenario = Scenario.create_default("scenario-alpha", "tenant-alpha")

    assert scenario.to_dict() == {
        "scenario_id": "scenario-alpha",
        "tenant": "tenant-alpha",
        "version": 1,
        "name": "scenario-alpha",
        "description": "scenario-alpha scenario",
        "created": FIXED_TIMESTAMP,
        "updated": FIXED_TIMESTAMP,
        "extras": {},
        "index_values": [],
    }


def test_from_dict_round_trip_with_nested_index_values() -> None:
    payload = {
        "scenario_id": "scenario-alpha",
        "tenant": "tenant-alpha",
        "version": 1,
        "name": "Scenario Alpha",
        "description": "Primary scenario",
        "created": "2026-05-15T10:00:00Z",
        "updated": "2026-05-15T11:00:00Z",
        "extras": {"kind": "scenario"},
        "index_values": [
            {
                "index_name": "visits",
                "index_value": {"mean": 12.5},
                "index_type": IndexType.CONSTANT.value,
            }
        ],
    }

    scenario = Scenario.from_dict(payload)

    assert isinstance(scenario.index_values[0], IndexEntry)
    assert scenario.index_values[0].to_dict() == payload["index_values"][0]
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
            "index_values": [],
        }
    )

    assert scenario.tenant == "tenant-beta"
    assert scenario.created == FIXED_TIMESTAMP
    assert scenario.updated == FIXED_TIMESTAMP
    assert scenario.index_values == []
