# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _as_tuple(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return default
    parts = [item.strip() for item in value.split(",")]
    return tuple(item for item in parts if item)


@dataclass(frozen=True, slots=True)
class AuthSettings:
    enabled: bool = False
    issuer: str | None = None
    audience: str | None = None
    jwks_url: str | None = None
    tenant_claim: str = "tenant_id"
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 30

    @classmethod
    def from_env(cls) -> "AuthSettings":
        return cls(
            enabled=_as_bool(os.getenv("AUTH_ENABLED"), default=False),
            issuer=os.getenv("AUTH_ISSUER") or None,
            audience=os.getenv("AUTH_AUDIENCE") or None,
            jwks_url=os.getenv("AUTH_JWKS_URL") or None,
            tenant_claim=os.getenv("AUTH_TENANT_CLAIM") or "tenant_id",
            algorithms=_as_tuple(
                os.getenv("AUTH_ALGORITHMS"),
                default=("RS256",),
            ),
            leeway_seconds=_as_int(
                os.getenv("AUTH_LEEWAY_SECONDS"),
                default=30,
            ),
        )


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings.from_env()
