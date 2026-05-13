# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.handler import Handler

_handler: Handler | None = None


def init_handler(handler: Handler) -> None:
    """Set the global handler instance. Call this before starting the app."""
    global _handler
    _handler = handler


def get_handler() -> Handler:
    """Return the current handler instance (used as a FastAPI dependency)."""
    if _handler is None:
        raise RuntimeError("Handler not initialized. Call init_handler() first.")
    return _handler
