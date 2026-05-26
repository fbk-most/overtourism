# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from overtourism.backend.auth.enums import AuthEnvironmentVariable, JwtDecodeOption
from overtourism.backend.auth.settings import AuthSettings


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    """Create and cache a JWKS client for the given URL.
    Reuse clients across requests to avoid repeated setup work."""
    return PyJWKClient(jwks_url)


def decode_jwt(token: str, settings: AuthSettings) -> dict[str, Any]:
    """Decode and validate a JWT using the configured auth settings.
    Apply issuer and audience checks only when those settings are provided."""
    if not settings.jwks_url:
        raise RuntimeError(
            f"{AuthEnvironmentVariable.JWKS_URL} must be set when {AuthEnvironmentVariable.ENABLED} is true"
        )

    signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token).key

    # Leeway gives exp/nbf checks a small clock-skew tolerance, while options
    # tells PyJWT which claim validations to enforce for this token.
    decode_kwargs: dict[str, Any] = {
        "algorithms": list(settings.algorithms),
        "leeway": settings.leeway_seconds,
        "options": {
            JwtDecodeOption.VERIFY_SIGNATURE: True,
            JwtDecodeOption.VERIFY_EXP: True,
            JwtDecodeOption.VERIFY_NBF: True,
            JwtDecodeOption.VERIFY_IAT: False,
            JwtDecodeOption.VERIFY_AUD: settings.audience is not None,
            JwtDecodeOption.VERIFY_ISS: settings.issuer is not None,
        },
    }

    if settings.audience is not None:
        decode_kwargs["audience"] = settings.audience
    if settings.issuer is not None:
        decode_kwargs["issuer"] = settings.issuer

    return jwt.decode(token, signing_key, **decode_kwargs)
