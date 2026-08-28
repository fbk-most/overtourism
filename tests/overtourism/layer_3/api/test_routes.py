# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from overtourism.layer_3.api.main import app
from overtourism.layer_3.model.common.sustainability_field import arrange_frontend_data


def test_evaluate_returns_frontend_shape_when_snapshot_is_false(monkeypatch) -> None:
    output = SimpleNamespace(
        field=[[0.1, 0.2]],
        samples_x=[12.0],
        samples_y=[34.0],
        uncertainty=[0.5],
        uncertainty_by_constraint={"parking": [0.6]},
        usage=[70],
        usage_by_constraint={"parking": [80]},
        usage_uncertainty=[0.1],
        usage_uncertainty_by_constraint={"parking": [0.2]},
        kpis={"critical constraint": {"name": "parking"}},
        x_max=100.0,
        y_max=200.0,
        capacity_mean=50.0,
        capacity_mean_by_constraint={"parking": 40.0},
        constraint_curves={"parking": [[1.0], [2.0]]},
    )
    output.to_snapshot = lambda: {
        "samples_x": output.samples_x,
        "samples_y": output.samples_y,
        "uncertainty": output.uncertainty,
        "uncertainty_by_constraint": output.uncertainty_by_constraint,
        "usage": output.usage,
        "usage_by_constraint": output.usage_by_constraint,
        "usage_uncertainty": output.usage_uncertainty,
        "usage_uncertainty_by_constraint": output.usage_uncertainty_by_constraint,
        "kpis": output.kpis,
        "x_max": output.x_max,
        "y_max": output.y_max,
        "capacity_mean": output.capacity_mean,
        "capacity_mean_by_constraint": output.capacity_mean_by_constraint,
        "constraint_curves": output.constraint_curves,
    }

    class FakeBackend:
        def evaluate(self, param_overrides):
            return output

        def arrange_data(self, data):
            return arrange_frontend_data(data)

    monkeypatch.setattr(
        "overtourism.layer_3.api.routes.get_backend", lambda model_key: FakeBackend()
    )

    with TestClient(app) as client:
        response = client.post(
            "/models/molveno/evaluate?as_snapshot=false",
            json={"param_overrides": {}},
        )

    assert response.status_code == 200
    assert response.json() == {
        "points": {
            "uncertainty": [
                {
                    "tourists": 12.0,
                    "excursionists": 34.0,
                    "index": 0.5,
                    "usage": 70,
                    "usage_uncertainty": 0.1,
                }
            ],
            "uncertainty_by_constraint": {
                "parking": [
                    {
                        "tourists": 12.0,
                        "excursionists": 34.0,
                        "index": 0.6,
                        "usage": 80,
                        "usage_uncertainty": 0.2,
                    }
                ]
            },
        },
        "kpis": {"critical constraint": {"name": "parking"}},
        "x_max": 100.0,
        "y_max": 200.0,
        "capacity_mean": 50.0,
        "capacity_mean_by_constraint": {"parking": 40.0},
        "constraint_curves": {"parking": [[1.0], [2.0]]},
    }


def test_evaluate_returns_snapshot_when_snapshot_is_true(monkeypatch) -> None:
    output = SimpleNamespace()

    class FakeBackend:
        def evaluate(self, param_overrides):
            return output

    monkeypatch.setattr(
        "overtourism.layer_3.api.routes.get_backend", lambda model_key: FakeBackend()
    )
    monkeypatch.setattr(
        "overtourism.layer_3.api.routes.EvaluateResponse.from_output",
        lambda data: {"field": [[0.1]]},
    )

    with TestClient(app) as client:
        response = client.post("/models/molveno/evaluate", json={})

    assert response.status_code == 200
    assert response.json() == {"field": [[0.1]]}


def test_get_schema_returns_model_indexes_and_frontend_metadata(monkeypatch) -> None:
    class FakeBackend:
        def schema(self):
            return {
                "metadata": {
                    "mapper": {
                        "default": "Tutti",
                        "parcheggi": "Parcheggi",
                        "spiaggia": "Spiaggia",
                        "alberghi": "Alberghi",
                        "ristoranti": "Ristoranti",
                    },
                    "color_map": [
                        [0.0, "rgb(5, 102, 8)"],
                        [0.05, "rgb(100, 180, 90)"],
                        [0.2, "rgb(180, 230, 170)"],
                        [0.4, "rgb(230, 250, 225)"],
                        [0.5, "yellow"],
                        [0.6, "rgb(255, 242, 242)"],
                        [0.8, "rgb(242, 204, 204)"],
                        [0.95, "rgb(204, 76, 76)"],
                        [1.0, "rgb(180, 4, 38)"],
                    ],
                    "kpi_mapper": {"title": "Indici"},
                    "plot_mapper": {
                        "monodimensional": {
                            "x": {"label": "Giorni"},
                            "y": {"label": "Utilizzo", "field": "usage"},
                        },
                        "bidimensional": {
                            "x": {"label": "Turisti", "field": "tourist"},
                            "y": {
                                "label": "Escursionisti",
                                "field": "excursionist",
                            },
                        },
                    },
                },
                "indexes": [{"name": "parking", "kind": "scalar"}],
            }

    monkeypatch.setattr(
        "overtourism.layer_3.api.routes.get_backend", lambda model_key: FakeBackend()
    )

    with TestClient(app) as client:
        response = client.get("/models/molveno/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"] == {
        "mapper": {
            "default": "Tutti",
            "parcheggi": "Parcheggi",
            "spiaggia": "Spiaggia",
            "alberghi": "Alberghi",
            "ristoranti": "Ristoranti",
        },
        "color_map": [
            [0.0, "rgb(5, 102, 8)"],
            [0.05, "rgb(100, 180, 90)"],
            [0.2, "rgb(180, 230, 170)"],
            [0.4, "rgb(230, 250, 225)"],
            [0.5, "yellow"],
            [0.6, "rgb(255, 242, 242)"],
            [0.8, "rgb(242, 204, 204)"],
            [0.95, "rgb(204, 76, 76)"],
            [1.0, "rgb(180, 4, 38)"],
        ],
        "kpi_mapper": {"title": "Indici"},
        "plot_mapper": {
            "monodimensional": {
                "x": {"label": "Giorni"},
                "y": {"label": "Utilizzo", "field": "usage"},
            },
            "bidimensional": {
                "x": {"label": "Turisti", "field": "tourist"},
                "y": {"label": "Escursionisti", "field": "excursionist"},
            },
        },
    }
    assert body["indexes"][0]["name"] == "parking"
    assert body["indexes"][0]["kind"] == "scalar"


def test_get_fazzon_schema_returns_fazzon_frontend_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/models/fazzon/schema")

    assert response.status_code == 200
    assert response.json()["metadata"] == {
        "mapper": {
            "default": "Tutti",
            "parking": "Parcheggi",
            "road": "Viabilità",
            "food": "Ristorazione",
            "lakeside": "Lungolago",
        },
        "color_map": [
            [0.0, "rgb(5, 102, 8)"],
            [0.05, "rgb(100, 180, 90)"],
            [0.2, "rgb(180, 230, 170)"],
            [0.4, "rgb(230, 250, 225)"],
            [0.5, "yellow"],
            [0.6, "rgb(255, 242, 242)"],
            [0.8, "rgb(242, 204, 204)"],
            [0.95, "rgb(204, 76, 76)"],
            [1.0, "rgb(180, 4, 38)"],
        ],
        "kpi_mapper": {
            "title": "Indici",
            "area": "Area Totale",
            "overtourism_level": "Giorni di criticità complessiva",
            "constraint level parking": "Giorni di criticità Parcheggi",
            "constraint level road": "Giorni di criticità Viabilità",
            "constraint level food": "Giorni di criticità Ristorazione",
            "constraint level lakeside": "Giorni di criticità Lungolago",
            "critical constraint": "Vincolo Critico",
        },
        "plot_mapper": {
            "monodimensional": {
                "x": {"label": "Giorni (ordinati per utilizzo)"},
                "y": {
                    "label": "Livello di utilizzo della destinazione",
                    "field": "usage",
                },
            },
            "bidimensional": {
                "x": {
                    "label": "Visitatori in auto / giorno",
                    "field": "visitors_car",
                },
                "y": {
                    "label": "Visitatori non-auto / giorno",
                    "field": "visitors_other",
                },
            },
        },
    }
