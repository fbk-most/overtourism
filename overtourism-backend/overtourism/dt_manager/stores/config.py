# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StoreConfig:
    """Configuration for storage backend construction.

    Parameters
    ----------
    store_type : str
        Registered store type name.
    config : dict, optional
        Keyword arguments forwarded to the store constructor.
    """

    store_type: str
    config: dict = field(default_factory=dict)
