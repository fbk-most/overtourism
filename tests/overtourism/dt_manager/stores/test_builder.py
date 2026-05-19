# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.stores.builder import create_store
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.dt_manager.stores.enums import StoreType


def test_create_store_returns_sql_implementation(tmp_path) -> None:
    sql_store = create_store(
        StoreType.SQL.value,
        url=f"sqlite:///{tmp_path / 'store.db'}",
    )

    assert isinstance(sql_store, SQLStore)


def test_create_store_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unknown store type"):
        create_store("missing", folder="/tmp/unused")
