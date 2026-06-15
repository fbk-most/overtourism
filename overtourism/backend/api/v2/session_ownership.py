# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import Index, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from overtourism.backend.auth.models import AuthContext

if typing.TYPE_CHECKING:
    from overtourism.backend.handler import Handler


class SessionOwnershipConflict(RuntimeError):
    """Raised when a session is already owned by a different user."""


class SessionOwnershipBase(DeclarativeBase):
    pass


class SessionOwnershipRecord(SessionOwnershipBase):
    __tablename__ = "session_ownership"
    __table_args__ = (Index("idx_session_ownership_owner", "tenant", "owner_id"),)

    tenant: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)


def resolve_session_owner_id(context: AuthContext, tenant: str) -> str:
    """Resolve the ownership key for the current request."""
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

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing user identity claim",
    )


def _session_not_found_detail(session_id: str) -> str:
    return f"Session '{session_id}' not found."


class SessionOwnershipStore:
    """Persist session ownership in a dedicated SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        SessionOwnershipBase.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            future=True,
        )

    def _get_record(
        self,
        db_session: Session,
        tenant: str,
        session_id: str,
    ) -> SessionOwnershipRecord | None:
        return db_session.get(
            SessionOwnershipRecord,
            (tenant, session_id),
        )

    def claim_session(
        self,
        tenant: str,
        session_id: str,
        owner_id: str,
    ) -> None:
        normalized_owner_id = owner_id.strip()
        if not normalized_owner_id:
            raise ValueError("owner_id must not be empty")

        with self.session_factory.begin() as db_session:
            record = self._get_record(db_session, tenant, session_id)
            if record is not None:
                if record.owner_id != normalized_owner_id:
                    raise SessionOwnershipConflict(
                        _session_not_found_detail(session_id)
                    )
                return

            db_session.add(
                SessionOwnershipRecord(
                    tenant=tenant,
                    session_id=session_id,
                    owner_id=normalized_owner_id,
                )
            )

    def read_session_owner(
        self,
        tenant: str,
        session_id: str,
    ) -> str | None:
        with self.session_factory() as db_session:
            record = self._get_record(db_session, tenant, session_id)
            if record is None:
                return None
            return record.owner_id

    def list_session_ids(
        self,
        tenant: str,
        owner_id: str,
    ) -> list[str]:
        with self.session_factory() as db_session:
            statement = (
                select(SessionOwnershipRecord.session_id)
                .where(SessionOwnershipRecord.tenant == tenant)
                .where(SessionOwnershipRecord.owner_id == owner_id)
                .order_by(SessionOwnershipRecord.session_id)
            )
            return list(db_session.scalars(statement))

    def delete_session(
        self,
        tenant: str,
        session_id: str,
    ) -> None:
        with self.session_factory.begin() as db_session:
            record = self._get_record(db_session, tenant, session_id)
            if record is not None:
                db_session.delete(record)


def require_session_ownership(
    handler: Handler,
    tenant: str,
    session_id: str,
    context: AuthContext,
) -> str:
    owner_id = resolve_session_owner_id(context, tenant)
    current_owner_id = _get_sos(handler).read_session_owner(tenant, session_id)
    if current_owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_session_not_found_detail(session_id),
        )
    return owner_id


def can_claim_session_ownership(
    handler: Handler,
    tenant: str,
    session_id: str,
    context: AuthContext,
) -> str:
    owner_id = resolve_session_owner_id(context, tenant)
    current_owner_id = _get_sos(handler).read_session_owner(tenant, session_id)
    if current_owner_id is not None and current_owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_session_not_found_detail(session_id),
        )
    return owner_id


def claim_session_ownership(
    handler: Handler,
    tenant: str,
    session_id: str,
    context: AuthContext,
) -> None:
    owner_id = resolve_session_owner_id(context, tenant)
    try:
        _get_sos(handler).claim_session(tenant, session_id, owner_id)
    except SessionOwnershipConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_session_not_found_detail(session_id),
        ) from exc


def list_owned_session_ids(
    handler: Handler,
    tenant: str,
    context: AuthContext,
) -> list[str]:
    owner_id = resolve_session_owner_id(context, tenant)
    return _get_sos(handler).list_session_ids(tenant, owner_id)


def delete_session_ownership(
    handler: Handler,
    tenant: str,
    session_id: str,
) -> None:
    _get_sos(handler).delete_session(tenant, session_id)


def _get_sos(handler: Handler) -> SessionOwnershipStore:
    store = handler.session_ownership_store
    if store is None:
        raise RuntimeError("Session ownership store not initialized")
    return store
