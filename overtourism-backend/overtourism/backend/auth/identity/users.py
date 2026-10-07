# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class UserRole(StrEnum):
    ADMIN = "admin"
    MULTIEDITOR = "multieditor"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    user_id: str
    identifier: str
    subject: str | None
    role: UserRole
    is_active: bool
    territories: frozenset[str]
    created_at: datetime
    updated_at: datetime


class UserRepository(Protocol):
    def load_users(self) -> list[User]: ...

    def save_user(self, user: User) -> None: ...

    def bind_subject_if_unlinked(self, identifier: str, subject: str) -> bool: ...

    def create_first_admin_if_empty(self, user: User) -> bool: ...
