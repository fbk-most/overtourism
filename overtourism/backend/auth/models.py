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
