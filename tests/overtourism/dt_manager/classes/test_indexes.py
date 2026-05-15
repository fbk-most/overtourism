# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.classes.indexes import IndexEntry, IndexType


def test_index_entry_round_trip() -> None:
    payload = {
        "index_name": "visits",
        "index_value": {"mean": 12.5, "stdev": 1.2},
        "index_type": IndexType.CONSTANT.value,
    }

    index_entry = IndexEntry.from_dict(payload)

    assert index_entry.to_dict() == payload
    assert index_entry.index_name == payload["index_name"]
    assert index_entry.index_value == payload["index_value"]
    assert index_entry.index_type == payload["index_type"]


def test_index_type_values_are_stable() -> None:
    assert IndexType.CONSTANT.value == "constant"
    assert IndexType.UNIFORM.value == "uniform"
    assert IndexType.LOGNORM.value == "lognorm"
    assert IndexType.TRIANG.value == "triang"
