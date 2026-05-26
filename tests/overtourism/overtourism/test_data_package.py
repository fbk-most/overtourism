# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.overtourism.data import OvertourismIndexesLoader, get_index_data_path


def test_get_index_data_path_points_to_packaged_assets() -> None:
    data_path = get_index_data_path()

    assert data_path.name == "index_data"
    assert (data_path / "map_comuni.geojson").is_file()
    assert (data_path / "df_tasso_ricettivita.parquet").is_file()


def test_loader_reads_packaged_catalog_and_assets() -> None:
    loader = OvertourismIndexesLoader(get_index_data_path())

    categories = loader.get_categories(language="en")
    indexes = loader.get_list(category="capacity", language="en")
    map_payload = loader.get_map("map_comuni")
    dataframe_payload = loader.get_dataframe("df_tasso_ricettivita")

    assert categories["capacity"] == "Capacity Indices"
    assert indexes["ricettivita"]["title"] == "Accommodation capacity index"
    assert map_payload["features"]
    assert dataframe_payload["data"]
