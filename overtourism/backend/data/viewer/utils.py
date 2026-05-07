# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, cast

from civic_digital_twins.dt_model.model.index import Distribution
from scipy import stats

from overtourism.backend.data.catalog import Language, SimIndexCatalog
from overtourism.backend.data.viewer.index import (
    VizConstIndex,
    VizIndex,
    VizLognormDistIndex,
    VizTriangDistIndex,
    VizUniformDistIndex,
)
from overtourism.dt_manager.classes.indexes import IndexType


def build_indexes_from_config(config: dict) -> list[VizIndex]:
    """Build a list of VizIndex instances from a YAML configuration dict."""
    indexes = []

    for idx_config in config["indexes"]:
        index_type = idx_config["index_type"]
        common_args = {
            "index_id": idx_config["index_id"],
            "index_name": idx_config["index_name"],
            "index_type": index_type,
            "group": idx_config["group"],
            "editable": idx_config.get("editable", True),
            "description": idx_config.get("description"),
            "index_category": idx_config.get("index_category"),
        }

        if index_type == IndexType.CONSTANT.value:
            indexes.append(
                VizConstIndex(
                    **common_args,
                    v=idx_config["v"],
                    min=idx_config["min"],
                    max=idx_config["max"],
                    step=idx_config["step"],
                )
            )
        elif index_type == IndexType.UNIFORM.value:
            indexes.append(
                VizUniformDistIndex(
                    **common_args,
                    loc=idx_config["loc"],
                    scale=idx_config["scale"],
                    min=idx_config["min"],
                    max=idx_config["max"],
                    step=idx_config["step"],
                )
            )
        elif index_type == IndexType.LOGNORM.value:
            indexes.append(
                VizLognormDistIndex(
                    **common_args,
                    loc=idx_config["loc"],
                    scale=idx_config["scale"],
                    s=idx_config["s"],
                    min=idx_config["min"],
                    max=idx_config["max"],
                    step=idx_config["step"],
                )
            )
        elif index_type == IndexType.TRIANG.value:
            indexes.append(
                VizTriangDistIndex(
                    **common_args,
                    loc=idx_config["loc"],
                    scale=idx_config["scale"],
                    c=idx_config["c"],
                    min=idx_config["min"],
                    max=idx_config["max"],
                    step=idx_config["step"],
                )
            )
        else:
            raise ValueError(f"Unknown index type: {index_type}")

    return indexes


def format_value(idx: VizIndex, value: Any) -> Any:
    """Convert a raw UI value to a model-compatible value using the index type."""
    if isinstance(idx, VizConstIndex):
        return value
    elif isinstance(idx, VizUniformDistIndex):
        (f, t) = value
        diff = max(t - f, 1e-04)
        return cast(Distribution, stats.uniform(loc=f, scale=diff))
    elif isinstance(idx, VizLognormDistIndex):
        return cast(Distribution, stats.lognorm(loc=idx.loc, scale=value, s=idx.s))
    elif isinstance(idx, VizTriangDistIndex):
        (f, t) = value
        diff = max(t - f, 1e-04)
        return cast(Distribution, stats.triang(loc=f, scale=diff, c=idx.c))
    return value


def prepare_values_for_eval(values: dict, indexes: list[VizIndex]) -> dict:
    """Prepare values from the frontend for model evaluation."""
    new_vals = {}
    for k, v in values.items():
        for i in indexes:
            if i.index_id == k:
                new_vals[k] = format_value(i, v)
    return new_vals


def build_indexes_from_catalog(
    catalog: SimIndexCatalog,
    language: Language = "it",
) -> list[VizIndex]:
    """Build VizIndex instances from a SimIndexCatalog for the given language."""
    return build_indexes_from_config(catalog.to_config(language))
