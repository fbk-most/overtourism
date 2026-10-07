# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

import numpy as np

from overtourism.dt_manager.utils.dictable import Dictable


class SampleEnum(Enum):
    ALPHA = "alpha"


class SampleDictable(Dictable):
    def __init__(self, required: str) -> None:
        self.required = required
        self.initialized = True


def test_to_dict_recursively_converts_nested_values() -> None:
    item = SampleDictable("root")
    item.enum_value = SampleEnum.ALPHA
    item.numpy_scalar = np.int64(7)
    item.numpy_array = np.array([1, 2], dtype=np.int64)
    item.mapping = {SampleEnum.ALPHA: np.int64(3)}
    item.sequence = (SampleEnum.ALPHA, np.int64(4))
    item.namespace = SimpleNamespace(answer=np.int64(42))

    assert item.to_dict() == {
        "required": "root",
        "initialized": True,
        "enum_value": "alpha",
        "numpy_scalar": 7,
        "numpy_array": [1, 2],
        "mapping": {"alpha": 3},
        "sequence": ["alpha", 4],
        "namespace": {"answer": 42},
    }


def test_from_dict_populates_attributes_without_running_init() -> None:
    payload = {"required": "root", "extra": "value"}

    item = SampleDictable.from_dict(payload)

    assert isinstance(item, SampleDictable)
    assert item.required == "root"
    assert item.extra == "value"
    assert item.__dict__ == payload
    assert not hasattr(item, "initialized")
