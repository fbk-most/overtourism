# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from importlib import import_module

import pytest

from overtourism.backend.api.shared.dependencies import get_handler


@pytest.mark.parametrize(
    ("module_name", "expected_paths", "expected_title"),
    [
        (
            "overtourism.overtourism.app_v1",
            ["/api/v1/{tenant}/data/overtourism/indexes/categories"],
            "AIxPA Over-Tourism API",
        ),
        (
            "overtourism.overtourism.app_v2",
            [
                "/api/v2/{tenant}/problems",
                "/api/v2/{tenant}/proposals",
                "/api/v2/{tenant}/scenarios",
                "/api/v2/{tenant}/data/overtourism/indexes/categories",
                "/api/v2/{tenant}/widgets",
            ],
            "Overtourism API",
        ),
    ],
)
def test_domain_app_builders_wire_overtourism_collaborators(
    module_name: str,
    expected_paths: list[str],
    expected_title: str,
) -> None:
    module = import_module(module_name)

    handler = module.build_handler()
    app = module.build_app()

    assert handler.viewer is not None
    assert handler.data_loader is not None
    assert handler.prepare_values_fn is not None
    assert callable(handler.arrange_data_fn)
    assert handler.manager.base_problem_config.tenant == "molveno"
    assert (
        handler.data_loader.get_categories(language="en")["capacity"]
        == "Capacity Indices"
    )
    paths = {route.path for route in app.routes}
    for expected_path in expected_paths:
        assert expected_path in paths
    assert app.title == expected_title


def test_app_v2_bootstrap_registers_the_molveno_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("overtourism.overtourism.app_v2")

    handler = module.build_handler()
    monkeypatch.setattr(module, "build_handler", lambda: handler)
    app = module.build_app()

    assert get_handler("molveno") is handler
    assert app.title == "Overtourism API"
