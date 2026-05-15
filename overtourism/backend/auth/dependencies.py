# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWTError

from overtourism.backend.auth.jwt import decode_jwt
from overtourism.backend.auth.models import AuthContext
from overtourism.backend.auth.settings import AuthSettings, get_auth_settings


def _resolve_request_tenant(request: Request, tenant: str | None) -> str | None:
    if tenant is not None:
        return tenant

    path_tenant = request.path_params.get("tenant")
    if path_tenant is not None:
        return str(path_tenant)

    query_tenant = request.query_params.get("tenant")
    if query_tenant:
        return query_tenant

    return None


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


def _claim_to_str(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def get_auth_context(
    request: Request,
    tenant: str | None = None,
    authorization: str | None = Header(default=None),
    settings: AuthSettings = Depends(get_auth_settings),
) -> AuthContext:
    resolved_tenant = _resolve_request_tenant(request, tenant)

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
            detail="Missing bearer token",
        )

    try:
        claims = dict(decode_jwt(token, settings))
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc

    token_tenant = _claim_to_str(claims.get(settings.tenant_claim))
    if resolved_tenant is not None and token_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token is missing tenant claim '{settings.tenant_claim}'",
        )
    if resolved_tenant is not None and token_tenant != resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token tenant does not match requested tenant",
        )

    subject = _claim_to_str(claims.get("sub"))
    return AuthContext(
        authenticated=True,
        tenant=resolved_tenant or token_tenant,
        subject=subject,
        token=token,
        claims=claims,
    )
