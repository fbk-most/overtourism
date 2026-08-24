# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import HTTPException, status

from overtourism.backend.auth.dependencies import Handler

_handler: Handler | None = None


def init_handler(handler: Handler) -> None:
    """Set the global handler instance used by the API layer."""
    global _handler
    _handler = handler


def get_handler() -> Handler:
    """Return the current handler instance."""
    try:
        if _handler is None:
            raise KeyError("handler not initialized")
        return _handler
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handler not initialized.",
        ) from exc
