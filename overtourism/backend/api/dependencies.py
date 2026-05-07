# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.backend.managers import Managers

_managers: Managers | None = None


def init_managers(managers: Managers) -> None:
    """Set the global managers instance. Call this before starting the app."""
    global _managers
    _managers = managers


def get_managers() -> Managers:
    """Return the current managers instance (used as a FastAPI dependency)."""
    if _managers is None:
        raise RuntimeError("Managers not initialized. Call init_managers() first.")
    return _managers
