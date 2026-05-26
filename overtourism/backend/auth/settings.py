# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from overtourism.backend.auth.enums import (
    AuthClaim,
    AuthEnvironmentVariable,
    JwtAlgorithm,
)

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class AuthSettings:
    enabled: bool = False
    issuer: str | None = None
    audience: str | None = None
    jwks_url: str | None = None
    tenant_claim: str = AuthClaim.TENANT
    algorithms: tuple[str, ...] = (JwtAlgorithm.RS256,)
    leeway_seconds: int = 30

    @classmethod
    def from_env(cls) -> "AuthSettings":
        enabled_value = os.getenv(AuthEnvironmentVariable.ENABLED)
        algorithms_value = os.getenv(AuthEnvironmentVariable.ALGORITHMS)
        leeway_value = os.getenv(AuthEnvironmentVariable.LEEWAY_SECONDS)
        return cls(
            enabled=enabled_value is not None
            and enabled_value.strip().lower() in _TRUTHY_ENV_VALUES,
            issuer=os.getenv(AuthEnvironmentVariable.ISSUER) or None,
            audience=os.getenv(AuthEnvironmentVariable.AUDIENCE) or None,
            jwks_url=os.getenv(AuthEnvironmentVariable.JWKS_URL) or None,
            tenant_claim=os.getenv(AuthEnvironmentVariable.TENANT_CLAIM)
            or AuthClaim.TENANT,
            algorithms=tuple(
                item.strip() for item in algorithms_value.split(",") if item.strip()
            )
            if algorithms_value and algorithms_value.strip()
            else (JwtAlgorithm.RS256,),
            leeway_seconds=int(leeway_value)
            if leeway_value and leeway_value.strip()
            else 30,
        )


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings.from_env()
