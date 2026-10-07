# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from overtourism.backend.auth.identity.user_manager import UserManager
    from overtourism.dt_manager.manager.manager import Manager


class Handler:
    """Container for backend managers shared by API dependencies."""

    def __init__(
        self,
        manager: Manager,
        user_manager: UserManager | None = None,
    ) -> None:
        self.manager = manager
        self.user_manager = user_manager


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
