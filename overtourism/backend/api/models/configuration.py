# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Index(BaseModel):
    name: str
    kind: str
    distribution_family: str | None
    distribution_fixed_params: dict[str, Any] | None
    support: list[Any] | None
    default: Any | None
    default_category: Any | None
    label: str
    description: str
    unit: str
    category: str
    step: float | None
    min_value: float | None
    max_value: float | None
    default_range: list[Any] | None


class Metadata(BaseModel):
    mapper: dict[str, str]
    color_map: list[list[float, str]]
    kpi_mapper: dict[str, str]
    plot_mapper: dict[str, dict[str, Any]]


class Configuration(BaseModel):
    metadata: Metadata
    indexes: list[Index]
