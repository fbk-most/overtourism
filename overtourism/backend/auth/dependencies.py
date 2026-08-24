# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from overtourism.backend.auth.enums import (
    AuthClaim,
    AuthErrorDetail,
    AuthHeaderScheme,
)
from overtourism.backend.auth.jwt import decode_jwt
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.auth.settings import AuthSettings, get_auth_settings
from overtourism.dt_manager.manager.manager import Manager

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


def _claim_as_strs(claims: Mapping[str, object], claim_name: str) -> tuple[str, ...]:
    """Read a claim value and normalize it to a tuple of strings."""
    value = claims.get(claim_name)
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value if item is not None)
    return (str(value),)


def _tenant_claim_error_detail(
    requested_tenant: str | None,
    token_tenants: tuple[str, ...],
    tenant_claim: str,
) -> str | None:
    """Validate the token tenant against the requested tenant.
    Return the HTTP error detail when the claim is missing or mismatched."""
    if requested_tenant is None:
        return None
    if not token_tenants:
        return f"Token is missing tenant claim '{tenant_claim}'"
    if requested_tenant not in token_tenants:
        return AuthErrorDetail.TENANT_MISMATCH
    return None


def _auth_context_tenant(
    requested_tenant: str | None,
    token_tenants: tuple[str, ...],
) -> str | None:
    """Choose the tenant exposed in the auth context."""
    if requested_tenant is not None:
        return requested_tenant
    if len(token_tenants) == 1:
        return token_tenants[0]
    return None


def get_auth_context(
    tenant: str | None = None,
    authorization: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_auth_scheme)
    ] = None,
    *,
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> AuthContext:
    """Build the auth context for the current request.
    When auth is enabled, validate the bearer token and tenant claim."""
    resolved_tenant = tenant

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

    token_tenants = _claim_as_strs(claims, settings.tenant_claim)
    tenant_error_detail = _tenant_claim_error_detail(
        requested_tenant=resolved_tenant,
        token_tenants=token_tenants,
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
        tenant=_auth_context_tenant(resolved_tenant, token_tenants),
        subject=subject_value,
        token=token,
        claims=claims,
    )


class Handler:
    """
    Container for backend singletons.
    """

    def __init__(
        self,
        manager: Manager,
    ) -> None:
        self.manager = manager
