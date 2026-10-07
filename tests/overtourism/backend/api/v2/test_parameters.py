# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.api.models.configuration import ModelSchema


def test_backend_model_schema_matches_layer_3_index_contract() -> None:
    schema = ModelSchema.model_validate(
        {
            "metadata": {
                "mapper": {},
                "color_map": [],
                "kpi_mapper": {},
                "plot_mapper": {},
            },
            "indexes": [
                {
                    "name": "visitors",
                    "kind": "scalar",
                    "distribution_family": None,
                    "distribution_fixed_params": None,
                    "support": ["default"],
                    "default": 0.69,
                    "default_category": None,
                    "label": "Visitors",
                    "description": "Visitor count",
                    "unit": "people",
                    "category": "tourism",
                    "step": None,
                    "min_value": None,
                    "max_value": None,
                    "default_range": [0.0, 1.0],
                }
            ],
        }
    )

    assert schema.indexes[0].support == ["default"]
    assert schema.indexes[0].default_range == (0.0, 1.0)


def test_configuration_returns_the_model_schema(monkeypatch, client, territory) -> None:
    monkeypatch.setattr(
        "overtourism.backend.api.v2.parameters.call_schema",
        lambda requested_territory: {
            "metadata": {
                "mapper": {},
                "color_map": [],
                "kpi_mapper": {},
                "plot_mapper": {"monodimensional": {}, "bidimensional": {}},
            },
            "indexes": [
                {"name": "visitors", "kind": "scalar", "support": []}
            ],
        },
    )

    response = client.get(f"/api/v2/{territory}/configuration")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"] == {
        "mapper": {},
        "color_map": [],
        "kpi_mapper": {},
        "plot_mapper": {"monodimensional": {}, "bidimensional": {}},
    }
    assert body["indexes"][0]["name"] == "visitors"
    assert body["indexes"][0]["kind"] == "scalar"
