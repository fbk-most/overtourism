# SPDX-License-Identifier: Apache-2.0
"""Smoke tests for the overtourism.api REST layer — catches wiring/schema breakage."""

import numpy as np
from fastapi.testclient import TestClient
from overtourism.api.main import app
from overtourism.cdt_ext.codec import decode_array

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
    def _check_snapshot(self, body: dict) -> None:
        field = decode_array(body["field"])
        assert field.shape == (101, 101)
        assert np.isfinite(field).all()
        assert ((field >= -1e-9) & (field <= 1.0 + 1e-9)).all()
        assert "value" in body["sustainability_index"]
        assert "ci" in body["sustainability_index"]

    def test_fazzon_default_scenario(self):
        resp = client.post("/models/fazzon/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 200
        self._check_snapshot(resp.json())

    def test_molveno_default_scenario(self):
        resp = client.post("/models/molveno/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 200
        self._check_snapshot(resp.json())

    def test_unknown_model_is_404(self):
        resp = client.post("/models/bogus/evaluate", json={"param_overrides": {}})
        assert resp.status_code == 404
