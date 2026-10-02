# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Boolean, DateTime, ForeignKey, String, select, text, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)

from overtourism.backend.auth.identity.users import User, UserRole


class AuthBase(DeclarativeBase):
    pass


class UserORM(AuthBase):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    identifier: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    territory_rows: Mapped[list[UserTerritoryORM]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class UserTerritoryORM(AuthBase):
    __tablename__ = "user_territories"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    territory: Mapped[str] = mapped_column(String, primary_key=True)
    user: Mapped[UserORM] = relationship(back_populates="territory_rows")


class SQLUserRepository:
    def __init__(
        self,
        engine: Engine,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory
        AuthBase.metadata.create_all(engine)

    def load_users(self) -> list[User]:
        statement = (
            select(UserORM)
            .options(selectinload(UserORM.territory_rows))
            .order_by(UserORM.user_id)
        )
        with self._session_factory() as session:
            return [self._to_user(row) for row in session.scalars(statement).all()]

    def save_user(self, user: User) -> None:
        with self._session_factory.begin() as session:
            self._save_user_in_session(session, user)

    def bind_subject_if_unlinked(self, identifier: str, subject: str) -> bool:
        try:
            with self._session_factory.begin() as session:
                result = cast(
                    CursorResult[Any],
                    session.execute(
                        update(UserORM)
                        .where(
                            UserORM.identifier == identifier,
                            UserORM.subject.is_(None),
                        )
                        .values(subject=subject, updated_at=datetime.now(UTC))
                    ),
                )
                return result.rowcount == 1
        except IntegrityError:
            return False

    def create_first_admin_if_empty(self, user: User) -> bool:
        if (
            user.role is not UserRole.ADMIN
            or user.subject is not None
            or user.territories
            or not user.is_active
        ):
            raise ValueError("The first user must be an active, unlinked global admin")

        try:
            with self._session_factory() as session:
                dialect_name = session.get_bind().dialect.name
                if dialect_name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                elif dialect_name == "postgresql":
                    session.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
                else:
                    raise RuntimeError(
                        f"First-admin bootstrap is unsupported for {dialect_name}"
                    )

                if session.scalar(select(UserORM.user_id).limit(1)) is not None:
                    session.rollback()
                    return False

                self._save_user_in_session(session, user)
                session.commit()
                return True
        except IntegrityError:
            return False

    def _save_user_in_session(self, session: Session, user: User) -> None:
        stored_user = session.get(UserORM, user.user_id)
        if stored_user is None:
            stored_user = UserORM(user_id=user.user_id)
            session.add(stored_user)

        stored_user.identifier = user.identifier
        stored_user.subject = user.subject
        stored_user.role = user.role.value
        stored_user.is_active = user.is_active
        stored_user.created_at = user.created_at
        stored_user.updated_at = user.updated_at
        stored_user.territory_rows = [
            UserTerritoryORM(territory=territory)
            for territory in sorted(user.territories)
        ]

    def _to_user(self, row: UserORM) -> User:
        return User(
            user_id=row.user_id,
            identifier=row.identifier,
            subject=row.subject,
            role=UserRole(row.role),
            is_active=row.is_active,
            territories=frozenset(
                territory_row.territory for territory_row in row.territory_rows
            ),
            created_at=self._as_utc(row.created_at),
            updated_at=self._as_utc(row.updated_at),
        )

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
