# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from overtourism.backend import handler as handler_module
from overtourism.backend.handler import Handler, get_handler, init_handler


def _build_handler() -> Handler:
    return Handler(manager=SimpleNamespace())


def test_get_handler_returns_initialized_handler() -> None:
    handler = _build_handler()

    init_handler(handler)

    assert get_handler() is handler


def test_get_handler_raises_when_not_initialized(monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "_handler", None)

    with pytest.raises(HTTPException) as exc_info:
        get_handler()

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Handler not initialized."
