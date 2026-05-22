# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("path", "params", "expected_call", "expected_body"),
    [
        (
            "/data/overtourism/indexes/categories",
            {"language": "en"},
            ("categories", {"language": "en"}),
            {"language": "en", "categories": ["pressure", "services"]},
        ),
        (
            "/data/overtourism/indexes/list",
            {"category": "pressure", "language": "it"},
            ("list", {"category": "pressure", "language": "it"}),
            {"category": "pressure", "language": "it", "indexes": ["visits"]},
        ),
        (
            "/data/overtourism/indexes/data",
            {"dataframe": "presence"},
            ("dataframe", {"dataframe": "presence"}),
            {"dataframe": "presence", "rows": [{"value": 1}]},
        ),
        (
            "/data/overtourism/indexes/map",
            {"map": "districts"},
            ("map", {"map": "districts"}),
            {"map": "districts", "features": [{"id": "feature-1"}]},
        ),
    ],
)
def test_data_routes_delegate_to_the_loader(
    client,
    data_loader,
    tenant: str,
    path: str,
    params: dict,
    expected_call: tuple[str, dict],
    expected_body: dict,
) -> None:
    response = client.get(f"/api/v2/{tenant}{path}", params=params)

    assert response.status_code == 200
    assert response.json() == expected_body
    assert data_loader.calls[-1] == expected_call
