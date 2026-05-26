# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import numpy as np
from scipy import stats

from overtourism.dt_manager.indexes.index import IndexType
from overtourism.dt_manager.scenario import values as values_module
from overtourism.dt_manager.scenario.values import scenario_values, values_as_scipy

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_scenario_values_serializes_constants_and_distributions(monkeypatch) -> None:
    monkeypatch.setattr(values_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    frozen_uniform = stats.uniform(loc=1.5, scale=2.0)
    frozen_lognorm = stats.lognorm(s=0.5, loc=0.0, scale=1.0)
    frozen_triang = stats.triang(c=0.25, loc=2.0, scale=4.0)

    scenario = scenario_values(
        "scenario-alpha",
        {
            "visits": np.int64(7),
            "uniform": frozen_uniform,
            "lognorm": frozen_lognorm,
            "triang": frozen_triang,
            "ignored": "skip",
            "array": np.array([1, 2, 3]),
        },
        name="Scenario Alpha",
        description="Primary scenario",
        extras={"kind": "scenario"},
        problem_id="problem-alpha",
    )

    assert scenario.created == FIXED_TIMESTAMP
    assert scenario.updated == FIXED_TIMESTAMP
    assert scenario.to_dict() == {
        "scenario_id": "scenario-alpha",
        "problem_id": "problem-alpha",
        "version": 1,
        "name": "Scenario Alpha",
        "description": "Primary scenario",
        "created": FIXED_TIMESTAMP,
        "updated": FIXED_TIMESTAMP,
        "extras": {"kind": "scenario"},
        "index_values": [
            {
                "index_name": "visits",
                "index_value": 7,
                "index_type": IndexType.CONSTANT.value,
            },
            {
                "index_name": "uniform",
                "index_value": {"loc": 1.5, "scale": 2.0},
                "index_type": IndexType.UNIFORM.value,
            },
            {
                "index_name": "lognorm",
                "index_value": {"s": 0.5, "loc": 0.0, "scale": 1.0},
                "index_type": IndexType.LOGNORM.value,
            },
            {
                "index_name": "triang",
                "index_value": {"c": 0.25, "loc": 2.0, "scale": 4.0},
                "index_type": IndexType.TRIANG.value,
            },
        ],
    }


def test_values_as_scipy_round_trip() -> None:
    scenario = scenario_values(
        "scenario-alpha",
        {
            "visits": np.int64(7),
            "uniform": stats.uniform(loc=1.5, scale=2.0),
            "lognorm": stats.lognorm(s=0.5, loc=0.0, scale=1.0),
            "triang": stats.triang(c=0.25, loc=2.0, scale=4.0),
        },
        problem_id="problem-alpha",
    )

    reconstructed = values_as_scipy(scenario)

    assert reconstructed["visits"] == 7
    assert reconstructed["uniform"].dist.name == "uniform"
    assert reconstructed["uniform"].kwds == {"loc": 1.5, "scale": 2.0}
    assert reconstructed["lognorm"].dist.name == "lognorm"
    assert reconstructed["lognorm"].kwds == {"s": 0.5, "loc": 0.0, "scale": 1.0}
    assert reconstructed["triang"].dist.name == "triang"
    assert reconstructed["triang"].kwds == {"c": 0.25, "loc": 2.0, "scale": 4.0}
