# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import orjson
import pandas as pd

from overtourism.overtourism.data.catalog import (
    OVERTOURISM_INDEX_CATALOG,
    IndexCatalog,
    Language,
)


class OvertourismIndexesLoader:
    def __init__(
        self,
        data_path: str | Path,
        *,
        catalog: IndexCatalog | None = None,
    ) -> None:
        self.data_path = Path(data_path)
        self.catalog = OVERTOURISM_INDEX_CATALOG if catalog is None else catalog
        self._maps: dict[str, dict[str, Any]] = {}
        self._dataframes: dict[str, pd.DataFrame] = {}

    def get_categories(self, language: Language = "it") -> dict[str, str]:
        return self.catalog.get_categories(language)

    def get_list(
        self,
        category: str = "",
        language: Language = "it",
    ) -> dict[str, dict[str, Any]]:
        return self.catalog.get_indexes(language, category)

    def _load_map(self, map_name: str, refresh: bool = False) -> None:
        if map_name not in self._maps or refresh:
            path = self.data_path / f"{map_name}.geojson"
            self._maps[map_name] = orjson.loads(path.read_bytes())

    def _load_data(self, dataframe_name: str, refresh: bool = False) -> None:
        if dataframe_name not in self._dataframes or refresh:
            path = self.data_path / f"{dataframe_name}.parquet"
            self._dataframes[dataframe_name] = pd.read_parquet(path).reset_index()

    def _jsonify_value(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {key: self._jsonify_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._jsonify_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._jsonify_value(item) for item in value]
        return value

    def get_map(self, map_: str) -> dict:
        self._load_map(map_)
        return self._maps[map_]

    def get_dataframe(self, df: str) -> dict:
        self._load_data(df)
        dict_ = self._jsonify_value(self._dataframes[df].to_dict(orient="records"))
        return {"data": dict_}
