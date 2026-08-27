# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.layer_3.dt_studio.dashboard.http_adapter import (
    HttpOvertourismAdapter,
)


def test_parameter_specs_reads_indexes_from_schema_response() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "metadata": {
                    "mapper": {},
                    "color_map": [],
                    "kpi_mapper": {},
                    "plot_mapper": {},
                },
                "indexes": [
                    {
                        "name": "parking capacity",
                        "kind": "distribution",
                        "default_range": [350.0, 450.0],
                    }
                ],
            }

    class FakeClient:
        def get(self, path: str) -> FakeResponse:
            assert path == "/models/molveno/schema"
            return FakeResponse()

    adapter = HttpOvertourismAdapter(
        model_key="molveno",
        title="Molveno",
        base_url="http://example.test",
    )
    adapter._client = FakeClient()

    specs = adapter.parameter_specs()

    assert len(specs) == 1
    assert specs[0].name == "parking capacity"
    assert specs[0].default_range == (350.0, 450.0)
