# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Mapping

from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWTError

from overtourism.backend.auth.enums import (
    AuthClaim,
    AuthErrorDetail,
    AuthHeaderScheme,
)
from overtourism.backend.auth.jwt import decode_jwt
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.auth.settings import AuthSettings, get_auth_settings


def _resolve_tenant(
    tenant: str | None,
    path_tenant: object | None,
    query_tenant: str | None,
) -> str | None:
    """Resolve the tenant from the explicit argument first.
    Fall back to path and then query parameters when needed."""
    if tenant is not None:
        return tenant
    if path_tenant is not None:
        return str(path_tenant)
    return query_tenant or None


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Extract a bearer token from the Authorization header.
    Return None when the header is missing, malformed, or empty."""
    if not authorization:
        return None

    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != AuthHeaderScheme.BEARER:
        return None

    token = raw_token.strip()
    return token or None


def _claim_as_str(claims: Mapping[str, object], claim_name: str) -> str | None:
    """Read a claim value and normalize it to a string.
    Return None when the claim is not present."""
    value = claims.get(claim_name)
    return None if value is None else str(value)


def _tenant_claim_error_detail(
    requested_tenant: str | None,
    token_tenant: str | None,
    tenant_claim: str,
) -> str | None:
    """Validate the token tenant against the requested tenant.
    Return the HTTP error detail when the claim is missing or mismatched."""
    if requested_tenant is None:
        return None
    if token_tenant is None:
        return f"Token is missing tenant claim '{tenant_claim}'"
    if token_tenant != requested_tenant:
        return AuthErrorDetail.TENANT_MISMATCH
    return None


def get_auth_context(
    request: Request,
    tenant: str | None = None,
    authorization: str | None = Header(default=None),
    settings: AuthSettings = Depends(get_auth_settings),
) -> AuthContext:
    """Build the auth context for the current request.
    When auth is enabled, validate the bearer token and tenant claim."""
    resolved_tenant = _resolve_tenant(
        tenant=tenant,
        path_tenant=request.path_params.get("tenant"),
        query_tenant=request.query_params.get("tenant"),
    )

    if not settings.enabled:
        return AuthContext(
            authenticated=False,
            tenant=resolved_tenant,
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

    token_tenant = _claim_as_str(claims, settings.tenant_claim)
    tenant_error_detail = _tenant_claim_error_detail(
        requested_tenant=resolved_tenant,
        token_tenant=token_tenant,
        tenant_claim=settings.tenant_claim,
    )
    if tenant_error_detail is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tenant_error_detail,
        )

    subject_value = _claim_as_str(claims, AuthClaim.SUBJECT)
    return AuthContext(
        authenticated=True,
        tenant=resolved_tenant or token_tenant,
        subject=subject_value,
        token=token,
        claims=claims,
    )
