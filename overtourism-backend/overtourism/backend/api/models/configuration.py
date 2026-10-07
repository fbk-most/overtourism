# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Index(BaseModel):
    name: str
    kind: str
    distribution_family: str | None = None
    distribution_fixed_params: dict[str, Any] | None = None
    support: list[str]
    default: float | None = None
    default_category: str | None = None
    label: str = ""
    description: str = ""
    unit: str = ""
    category: str = ""
    step: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_range: tuple[float, float] | None = None


class Metadata(BaseModel):
    mapper: dict[str, str]
    color_map: list[tuple[float, str]]
    kpi_mapper: dict[str, str]
    plot_mapper: dict[str, dict[str, Any]]


class ModelSchema(BaseModel):
    metadata: Metadata
    indexes: list[Index]
