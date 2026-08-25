# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


def test_configuration_returns_the_model_schema(monkeypatch, client, tenant) -> None:
    monkeypatch.setattr(
        "overtourism.backend.api.v2.parameters.call_schema",
        lambda requested_tenant: {
            "metadata": {"mapper": {}, "color_map": []},
            "indexes": [{"name": "visitors", "kind": "scalar"}],
        },
    )

    response = client.get(f"/api/v2/{tenant}/configuration")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"] == {"mapper": {}, "color_map": []}
    assert body["indexes"][0]["name"] == "visitors"
    assert body["indexes"][0]["kind"] == "scalar"
