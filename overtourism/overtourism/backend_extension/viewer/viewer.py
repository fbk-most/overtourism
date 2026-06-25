# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from numbers import Real

from overtourism.dt_manager.indexes.index import IndexType
from overtourism.dt_manager.indexes.utils import (
    VizIndex,
    build_indexes_from_config,
    prepare_values_for_eval,
)
from overtourism.overtourism.backend_extension.data import Language, SimIndexCatalog


def build_indexes_from_catalog(
    catalog: SimIndexCatalog,
    language: Language = "it",
) -> list[VizIndex]:
    """Build VizIndex instances from a SimIndexCatalog for the given language."""
    return build_indexes_from_config(catalog.to_config(language))


class ModelViewer:
    """Overtourism model viewer — manages widget configuration from a catalog.

    Provides:
    - ``get_widgets(vals, language)`` — widget dicts for the frontend
    - ``get_groups(language)`` — parameter groups
    - ``prepare_values(values)`` — convert raw UI values for evaluation
    """

    def __init__(self, catalog: SimIndexCatalog) -> None:
        self._catalog = catalog

    def _build_groups(self, language: Language = "it") -> list:
        groups: dict = {}
        for entry in self._catalog.entries:
            group_id = entry.group.it
            if group_id not in groups:
                groups[group_id] = {
                    "id": group_id,
                    "label": entry.group.resolve(language),
                    "parameters": [],
                }
        return list(groups.values())

    def get_groups(self, language: Language = "it") -> list:
        return self._build_groups(language)

    def get_widget_ids_by_groups(
        self,
        groups: list[str],
        language: Language = "it",
    ) -> list[str]:
        if not groups:
            return []

        indexes = build_indexes_from_catalog(self._catalog, language)
        return [index.index_id for index in indexes if index.group in groups]

    def get_widgets(self, vals: dict, language: Language = "it") -> dict:
        indexes = build_indexes_from_catalog(self._catalog, language)
        widgets: dict = {}
        for i in indexes:
            idx = i
            group_id = idx.group
            if group_id not in widgets:
                widgets[group_id] = []
            if idx.index_id in vals:
                if idx.index_type == IndexType.CONSTANT.value:
                    idx.v = _display_value(idx, vals[idx.index_id])
                else:
                    raw = vals[idx.index_id]
                    value = raw.kwds if hasattr(raw, "kwds") else raw
                    idx.loc = value["loc"]
                    idx.scale = value["scale"]
            widgets[group_id].append(idx.to_dict())
        return widgets

    def prepare_values(self, values: dict) -> dict:
        indexes = build_indexes_from_catalog(self._catalog)
        prepared_values = prepare_values_for_eval(values, indexes)
        index_by_id = {index.index_id: index for index in indexes}
        for key, value in prepared_values.items():
            idx = index_by_id.get(key)
            if idx is not None:
                prepared_values[key] = _model_value(idx, value)
        return prepared_values


def _is_real_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _display_value(idx: VizIndex, value: object) -> object:
    if idx.index_category == "%" and _is_real_number(value):
        numeric_value = float(value)
        return numeric_value * 100.0 if abs(numeric_value) <= 1.0 else numeric_value
    return value


def _model_value(idx: VizIndex, value: object) -> object:
    if idx.index_category == "%" and _is_real_number(value):
        numeric_value = float(value)
        return numeric_value / 100.0 if abs(numeric_value) > 1.0 else numeric_value
    return value
