# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from overtourism.backend.auth.settings import AuthSettings


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def decode_jwt(token: str, settings: AuthSettings) -> dict[str, Any]:
    if not settings.jwks_url:
        raise RuntimeError("AUTH_JWKS_URL must be set when AUTH_ENABLED is true")

    signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token).key

    decode_kwargs: dict[str, Any] = {
        "algorithms": list(settings.algorithms),
        "leeway": settings.leeway_seconds,
        "options": {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": False,
            "verify_aud": settings.audience is not None,
            "verify_iss": settings.issuer is not None,
        },
    }

    if settings.audience is not None:
        decode_kwargs["audience"] = settings.audience
    if settings.issuer is not None:
        decode_kwargs["issuer"] = settings.issuer

    return jwt.decode(token, signing_key, **decode_kwargs)
