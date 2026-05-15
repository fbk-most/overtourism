# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType


def test_store_config_defaults_to_empty_config() -> None:
    config = StoreConfig(store_type=StoreType.LOCAL.value)

    assert config.store_type == StoreType.LOCAL.value
    assert config.config == {}


def test_store_config_keeps_custom_config() -> None:
    config = StoreConfig(
        store_type=StoreType.SQL.value,
        config={"url": "sqlite:///store.db"},
    )

    assert config.store_type == StoreType.SQL.value
    assert config.config == {"url": "sqlite:///store.db"}
