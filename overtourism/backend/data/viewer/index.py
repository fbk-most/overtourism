# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from copy import copy
from dataclasses import dataclass


@dataclass
class VizIndex:
    index_id: str
    index_name: str
    index_type: str
    group: str
    editable: bool = True
    description: str | None = None
    index_category: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def copy(self) -> VizIndex:
        return copy(self)


@dataclass
class VizConstIndex(VizIndex):
    v: float = 0.0
    min: float = 0.0
    max: float = 0.0
    step: float = 1.0


@dataclass
class VizUniformDistIndex(VizIndex):
    loc: float = 0.0
    scale: float = 0.0
    min: float = 0.0
    max: float = 0.0
    step: float = 1.0


@dataclass
class VizLognormDistIndex(VizIndex):
    loc: float = 0.0
    scale: float = 0.0
    s: float = 0.0
    min: float = 0.0
    max: float = 0.0
    step: float = 1.0


@dataclass
class VizTriangDistIndex(VizIndex):
    loc: float = 0.0
    scale: float = 0.0
    c: float = 0.0
    min: float = 0.0
    max: float = 0.0
    step: float = 1.0
