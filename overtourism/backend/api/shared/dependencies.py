# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import HTTPException, status

from overtourism.backend.handler import Handler

_handler_registry: dict[str, Handler] = {}


def init_handler(handler: Handler) -> None:
    """Set the default handler instance for its tenant."""
    tenant = handler.manager.base_problem_config.tenant
    global _handler_registry
    _handler_registry = {tenant: handler}


def register_handler(tenant: str, handler: Handler) -> None:
    """Register a handler for a tenant."""
    _handler_registry[tenant] = handler


def get_handler(tenant: str) -> Handler:
    """Return the current handler instance for the requested tenant."""
    if not _handler_registry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found.",
        )

    try:
        return _handler_registry[tenant]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant not found: {tenant}.",
        ) from exc
