# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.overtourism.backend_extension.data.catalog import (
    LocalizedText,
    SimIndexCatalog,
    SimIndexEntry,
)
from overtourism.overtourism.backend_extension.viewer.viewer import ModelViewer


def test_model_viewer_round_trips_percentage_widgets() -> None:
    catalog = SimIndexCatalog(
        entries=(
            SimIndexEntry(
                index_id="tourists_parking_percentage",
                index_type="constant",
                index_name=LocalizedText(
                    it="Percentuale di turisti che usano i parcheggi",
                    en="Percentage of tourists using parking",
                ),
                group=LocalizedText(it="Parcheggi", en="Parking"),
                description=LocalizedText(it="Descrizione", en="Description"),
                min=0.0,
                max=100.0,
                step=1.0,
                index_category="%",
                v=2.0,
            ),
            SimIndexEntry(
                index_id="available_parking_spaces",
                index_type="constant",
                index_name=LocalizedText(
                    it="Numero di posti auto disponibili",
                    en="Number of available parking spaces",
                ),
                group=LocalizedText(it="Parcheggi", en="Parking"),
                description=LocalizedText(it="Descrizione", en="Description"),
                min=0.0,
                max=1000.0,
                step=10.0,
                v=350.0,
            ),
        )
    )
    viewer = ModelViewer(catalog)

    widgets = viewer.get_widgets(
        {
            "tourists_parking_percentage": 0.8,
            "available_parking_spaces": 350.0,
        }
    )
    widgets_by_id = {item["index_id"]: item for item in widgets["Parcheggi"]}
    assert widgets_by_id["tourists_parking_percentage"]["v"] == 80.0
    assert widgets_by_id["available_parking_spaces"]["v"] == 350.0

    assert viewer.prepare_values(
        {
            "tourists_parking_percentage": 80.0,
            "available_parking_spaces": 350.0,
        }
    ) == {
        "tourists_parking_percentage": 0.8,
        "available_parking_spaces": 350.0,
    }
