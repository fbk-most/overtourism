# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from overtourism.backend.auth.tokens.context import AuthContext
from overtourism.backend.auth.tokens.enums import (
    AuthClaim,
    AuthErrorDetail,
    AuthHeaderScheme,
)
from overtourism.backend.auth.tokens.jwt import decode_jwt
from overtourism.backend.auth.tokens.settings import AuthSettings, get_auth_settings

bearer_auth_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def _extract_bearer_token(
    authorization: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Extract a bearer token from the Authorization header.
    Return None when the header is missing, malformed, or empty."""
    if not authorization:
        return None

    if authorization.scheme.lower() != AuthHeaderScheme.BEARER:
        return None

    token = authorization.credentials.strip()
    return token or None


def _claim_as_str(claims: Mapping[str, object], claim_name: str) -> str | None:
    """Read a claim value and normalize it to a string.
    Return None when the claim is not present."""
    value = claims.get(claim_name)
    return None if value is None else str(value)


def get_auth_context(
    authorization: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_auth_scheme)
    ] = None,
    *,
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> AuthContext:
    """Build the auth context for the current request.
    When auth is enabled, validate the bearer token."""

    if not settings.enabled:
        return AuthContext(
            authenticated=False,
            subject=None,
            token=None,
            claims={},
        )

    token = _extract_bearer_token(authorization)

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AuthErrorDetail.MISSING_BEARER_TOKEN,
        )

    try:
        claims = dict(decode_jwt(token, settings))
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AuthErrorDetail.INVALID_BEARER_TOKEN,
        ) from exc

    subject_value = _claim_as_str(claims, AuthClaim.SUBJECT)
    return AuthContext(
        authenticated=True,
        subject=subject_value,
        token=token,
        claims=claims,
    )
