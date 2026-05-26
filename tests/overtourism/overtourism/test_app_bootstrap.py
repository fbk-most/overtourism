# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("module_name", "expected_path", "expected_title"),
    [
        (
            "overtourism.overtourism.app_v1",
            "/api/v1/{tenant}/data/overtourism/indexes/categories",
            "AIxPA Over-Tourism API",
        ),
        (
            "overtourism.overtourism.app_v2",
            "/api/v2/{tenant}/data/overtourism/indexes/categories",
            "Overtourism API",
        ),
    ],
)
def test_domain_app_builders_wire_overtourism_collaborators(
    module_name: str,
    expected_path: str,
    expected_title: str,
) -> None:
    module = import_module(module_name)

    handler = module.build_handler()
    app = module.build_app()

    assert handler.viewer is not None
    assert handler.data_loader is not None
    assert handler.prepare_values_fn is not None
    assert callable(handler.arrange_data_fn)
    assert (
        handler.data_loader.get_categories(language="en")["capacity"]
        == "Capacity Indices"
    )
    assert expected_path in {route.path for route in app.routes}
    assert app.title == expected_title
