# SPDX-License-Identifier: Apache-2.0
"""Smoke tests for the overtourism.api REST layer — catches wiring/schema breakage."""

from fastapi.testclient import TestClient
from overtourism.api.main import app

client = TestClient(app)


class TestListModels:
    def test_returns_fazzon_and_molveno(self):
        resp = client.get("/models")
        assert resp.status_code == 200
        keys = {m["key"] for m in resp.json()}
        assert keys == {"fazzon", "molveno"}


class TestSchema:
    def test_fazzon_schema(self):
        resp = client.get("/models/fazzon/schema")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_molveno_schema(self):
        resp = client.get("/models/molveno/schema")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_unknown_model_is_404(self):
        resp = client.get("/models/bogus/schema")
        assert resp.status_code == 404


class TestEvaluate:
    _EXPECTED_KEYS = {
        "field",
        "field_elements",
        "x_values",
        "y_values",
        "x_axis_name",
        "y_axis_name",
        "samples_x",
        "samples_y",
        "confidence",
        "sustainable_area",
        "sustainability_index",
        "sustainability_by_constraint",
        "modal_lines",
        "x_max",
        "y_max",
        "uncertainty",
        "uncertainty_by_constraint",
        "usage",
        "usage_by_constraint",
        "usage_uncertainty",
        "usage_uncertainty_by_constraint",
        "capacity_mean",
        "capacity_mean_by_constraint",
        "kpis",
        "constraint_curves",
    }

    def _check_response(self, body: dict) -> None:
        assert set(body.keys()) == self._EXPECTED_KEYS
        # Plain JSON, not base64: field is a nested list of numbers.
        assert len(body["field"]) == 101
        assert len(body["field"][0]) == 101
        assert all(-1e-9 <= v <= 1.0 + 1e-9 for row in body["field"] for v in row)
        assert len(body["usage"]) == len(body["samples_x"])
        assert body["capacity_mean"] == 100.0
        assert "overtourism_level" in body["kpis"]

    def test_fazzon_default_scenario(self):
        resp = client.post("/models/fazzon/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 200
        self._check_response(resp.json())

    def test_molveno_default_scenario(self):
        resp = client.post("/models/molveno/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 200
        self._check_response(resp.json())

    def test_unknown_model_is_404(self):
        resp = client.post("/models/bogus/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 404
