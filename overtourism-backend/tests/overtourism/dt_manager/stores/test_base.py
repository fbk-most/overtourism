# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.stores.classes.base import Store


def test_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        Store()
