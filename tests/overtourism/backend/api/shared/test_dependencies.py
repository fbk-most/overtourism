# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from overtourism.backend.api.shared.dependencies import (
    get_handler,
    init_handler,
    register_handler,
)
from overtourism.backend.handler import Handler


def _build_handler(tenant: str) -> Handler:
    manager = SimpleNamespace(name_cfg=SimpleNamespace(tenant=tenant))
    return Handler(manager=manager)


def test_get_handler_resolves_registered_handler_by_tenant() -> None:
    molveno_handler = _build_handler("molveno")
    fazzon_handler = _build_handler("fazzon")

    init_handler(molveno_handler)
    register_handler("fazzon", fazzon_handler)

    assert get_handler("molveno") is molveno_handler
    assert get_handler("fazzon") is fazzon_handler


def test_get_handler_raises_for_unknown_tenant() -> None:
    init_handler(_build_handler("molveno"))

    with pytest.raises(HTTPException) as exc_info:
        get_handler("fazzon")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Tenant not found: fazzon."
