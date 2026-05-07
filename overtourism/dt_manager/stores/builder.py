# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.classes.local.store import LocalIOStore
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.dt_manager.stores.enums import StoreType

_STORE_REGISTRY: dict[str, type[Store]] = {
    StoreType.LOCAL.value: LocalIOStore,
    StoreType.SQL.value: SQLStore,
}


def create_store(store_type: str, **kwargs: Any) -> Store:
    """Create a store instance by type name.

    Parameters
    ----------
    store_type : str
        Registered store type name.
    **kwargs : Any
        Keyword arguments forwarded to the store constructor.

    Returns
    -------
    Store
        Instantiated store.

    Raises
    ------
    ValueError
        If ``store_type`` is not registered.
    """
    try:
        cls = _STORE_REGISTRY[store_type]
    except KeyError:
        raise ValueError(
            f"Unknown store type: {store_type!r}. Available: {list(_STORE_REGISTRY)}"
        )
    return cls(**kwargs)
