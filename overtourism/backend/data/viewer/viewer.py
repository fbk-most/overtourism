# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.data.catalog import Language, SimIndexCatalog
from overtourism.backend.data.viewer.utils import (
    build_indexes_from_catalog,
    prepare_values_for_eval,
)
from overtourism.dt_manager.classes.indexes import IndexType


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
            group_id = entry.group.it  # Italian string as stable group ID
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
            group_id = idx.group  # Italian string, backward compatible
            if group_id not in widgets:
                widgets[group_id] = []
            if idx.index_id in vals:
                if idx.index_type == IndexType.CONSTANT.value:
                    idx.v = vals[idx.index_id]
                else:
                    raw = vals[idx.index_id]
                    value = raw.kwds if hasattr(raw, "kwds") else raw
                    idx.loc = value["loc"]
                    idx.scale = value["scale"]
            widgets[group_id].append(idx.to_dict())
        return widgets

    def prepare_values(self, values: dict) -> dict:
        # Language doesn't affect value shapes, use default Italian
        indexes = build_indexes_from_catalog(self._catalog)
        return prepare_values_for_eval(values, indexes)
