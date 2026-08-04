# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from numbers import Real
from typing import Any

from scipy import stats

from overtourism.dt_manager.indexes.index import IndexEntry, IndexType
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.utils.utils import get_timestamp


def scenario_values(
    scenario_id: str,
    tenant: str,
    values: dict,
    name: str | None = None,
    description: str | None = None,
    created: str | None = None,
    updated: str | None = None,
    extras: dict | None = None,
    version: int = 1,
) -> Scenario:
    """Build a storage-ready scenario from evaluator values."""
    now = get_timestamp()
    created = now if created is None else created
    updated = created if updated is None else updated
    indexes = _prepare_indexes(values)
    return Scenario(
        scenario_id=scenario_id,
        tenant=tenant,
        version=version,
        name=name,
        description=description,
        created=created,
        updated=updated,
        extras={} if extras is None else extras,
        index_values=indexes,
    )


def _prepare_indexes(values: dict[str, Any]) -> list[IndexEntry]:
    """Convert model values into serialized index entries."""
    indexes = []
    for key, value in values.items():
        if not isinstance(value, (Real, stats._distn_infrastructure.rv_frozen)):
            continue
        elif isinstance(value, stats._distn_infrastructure.rv_frozen):
            indexes.append(IndexEntry(key, value.kwds, value.dist.name))
        else:
            indexes.append(
                IndexEntry(key, _normalize_scalar(value), IndexType.CONSTANT.value)
            )
    return indexes


def _normalize_scalar(value: Any) -> Any:
    """Normalize scalar-like values to plain Python objects."""
    return (
        value.item()
        if hasattr(value, "item") and not isinstance(value, (dict, list))
        else value
    )


def values_as_scipy(scenario_data: Scenario) -> dict[str, Any]:
    """Reconstruct SciPy values from stored scenario index entries.

    Parameters
    ----------
    scenario_data : Scenario
        Scenario containing stored index entries.

    Returns
    -------
    dict
        Reconstructed model values.
    """
    values = {}
    for val in scenario_data.index_values:
        match val.index_type:
            case IndexType.CONSTANT.value:
                values[val.index_name] = val.index_value
            case IndexType.UNIFORM.value:
                values[val.index_name] = stats.uniform(
                    loc=val.index_value["loc"], scale=val.index_value["scale"]
                )
            case IndexType.LOGNORM.value:
                values[val.index_name] = stats.lognorm(
                    loc=val.index_value["loc"],
                    scale=val.index_value["scale"],
                    s=val.index_value["s"],
                )
            case IndexType.TRIANG.value:
                values[val.index_name] = stats.triang(
                    loc=val.index_value["loc"],
                    scale=val.index_value["scale"],
                    c=val.index_value["c"],
                )
    return values
