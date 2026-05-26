# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from overtourism.dt_manager.utils.dictable import Dictable


@dataclass
class IndexEntry(Dictable):
    """Serialized representation of a model index.

    Parameters
    ----------
    index_name : str
        Name of the index.
    index_value : dict | float
        Serialized index payload.
    index_type : str
        Index type name.
    """

    index_name: str
    index_value: dict | float
    index_type: str


class IndexType(StrEnum):
    """Supported parameter types for model indexes."""

    CONSTANT = "constant"
    UNIFORM = "uniform"
    LOGNORM = "lognorm"
    TRIANG = "triang"
