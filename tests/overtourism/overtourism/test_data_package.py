# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import orjson
import pandas as pd

from overtourism.overtourism.data import OvertourismIndexesLoader, get_index_data_path


def test_get_index_data_path_returns_package_index_data_location() -> None:
    data_path = get_index_data_path()

    assert data_path.name == "index_data"
    assert data_path.parent.name == "data"


def test_loader_reads_catalog_and_assets_from_local_data_directory(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "index_data"
    data_path.mkdir()
    (data_path / "map_comuni.geojson").write_bytes(
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"com_code": "001"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [11.0, 46.0],
                        },
                    }
                ],
            }
        )
    )
    pd.DataFrame(
        [
            {
                "ID": "001",
                "ricettivita": 0.25,
                "popolazione": 100,
                "posti_letto": 25,
            }
        ]
    ).to_parquet(data_path / "df_tasso_ricettivita.parquet")

    loader = OvertourismIndexesLoader(data_path)

    categories = loader.get_categories(language="en")
    indexes = loader.get_list(category="capacity", language="en")
    map_payload = loader.get_map("map_comuni")
    dataframe_payload = loader.get_dataframe("df_tasso_ricettivita")

    assert categories["capacity"] == "Capacity Indices"
    assert indexes["ricettivita"]["title"] == "Accommodation capacity index"
    assert map_payload["features"][0]["properties"]["com_code"] == "001"
    assert dataframe_payload["data"][0]["ricettivita"] == 0.25
