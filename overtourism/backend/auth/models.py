# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    authenticated: bool
    tenant: str | None = None
    subject: str | None = None
    token: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


def resolve_session_owner_id(context: AuthContext, tenant: str) -> str:
    """Resolve the stable owner identifier for a session."""
    if not context.authenticated:
        return f"anonymous:{tenant}"

    email = context.claims.get("email")
    if email is not None:
        email_value = str(email).strip()
        if email_value:
            return email_value

    if context.subject is not None:
        subject_value = context.subject.strip()
        if subject_value:
            return subject_value

    raise ValueError("Missing user identity claim")
