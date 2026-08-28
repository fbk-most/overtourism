# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.layer_3.model.common.sustainability_field import get_index_diffs


def test_get_index_diffs_formats_scalar_categorical_and_distribution_changes() -> None:
    schema = {
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

    assert get_index_diffs(
        schema,
        {
            "season": "peak",
            "parking capacity": [120.0, 240.0],
            "car mode share": 0.8,
        },
    ) == {
        "season": "base -> peak",
        "parking capacity": "100-200 -> 120-240",
        "car mode share": "0.69 -> 0.8",
    }


def test_get_index_diffs_uses_all_as_categorical_base_and_omits_unchanged_values() -> None:
    schema = {
        "indexes": [
            {"name": "weekday", "kind": "categorical"},
            {"name": "capacity", "kind": "distribution", "default_range": [10, 20]},
            {"name": "shuttle trips", "kind": "scalar", "default": 0.0},
        ]
    }

    assert get_index_diffs(
        schema,
        {
            "weekday": "saturday",
            "capacity": (10.0, 20.0),
            "shuttle trips": 0,
            "unknown": 3,
        },
    ) == {"weekday": "(tutte) -> saturday"}
