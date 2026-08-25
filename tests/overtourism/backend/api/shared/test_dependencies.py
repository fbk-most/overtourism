# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from overtourism.backend.api.utils import dependencies as dependencies_module
from overtourism.backend.api.utils.dependencies import get_handler, init_handler
from overtourism.backend.auth.dependencies import Handler


def _build_handler() -> Handler:
    return Handler(manager=SimpleNamespace())


def test_get_handler_returns_initialized_handler() -> None:
    handler = _build_handler()

    init_handler(handler)

    assert get_handler() is handler


def test_get_handler_raises_when_not_initialized(monkeypatch) -> None:
    monkeypatch.setattr(dependencies_module, "_handler", None)

    with pytest.raises(HTTPException) as exc_info:
        get_handler()

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Handler not initialized."
