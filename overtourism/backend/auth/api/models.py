# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from overtourism.backend.auth.identity.users import UserRole


class AuthMeResponse(BaseModel):
    authenticated: bool
    subject: str | None = None
    user_id: str | None = None
    role: UserRole | None = None
    is_global_admin: bool = False
    territories: list[str] = Field(default_factory=list)


class AuthRoleResponse(BaseModel):
    role: UserRole
    description: str


class AuthUserResponse(BaseModel):
    user_id: str
    identifier: str
    subject: str | None = None
    role: UserRole
    is_active: bool
    territories: list[str]
    created_at: datetime
    updated_at: datetime


class CreateAuthUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str
    role: UserRole
    territories: list[str] = Field(default_factory=list)


class UpdateAuthUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    territories: list[str] | None = None
    is_active: bool | None = None
