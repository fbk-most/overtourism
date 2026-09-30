# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.session.config import SessionCleanupConfig
from overtourism.dt_manager.session.session import Session
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from overtourism.dt_manager.utils.utils import get_timestamp, parse_timestamp


class SessionManager:
    """Persist session state and the draft/evaluation workflow."""

    def __init__(
        self,
        store: Store,
        cleanup_config: SessionCleanupConfig | None = None,
    ) -> None:
        self.store = store
        self.cleanup_config = cleanup_config or SessionCleanupConfig()

    def _is_expired(self, session_data: dict, now: datetime | None = None) -> bool:
        try:
            created = parse_timestamp(session_data["created"])
        except (KeyError, TypeError, ValueError):
            return True

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        cutoff = current_time.astimezone(UTC) - timedelta(
            seconds=self.cleanup_config.session_scenario_ttl_seconds
        )
        return created <= cutoff

    def _load_active_session_data(self, session_id: str) -> dict:
        session_data = self.store.load_session(session_id)
        if self._is_expired(session_data):
            raise EntityDoesNotExist(f"Session '{session_id}' not found")
        return session_data

    def require_active_session(self, session_id: str) -> None:
        """Raise when the session is absent or has exceeded its configured TTL."""
        self._load_active_session_data(session_id)

    def delete_expired_sessions(self, now: datetime | None = None) -> int:
        """Delete expired sessions and their temporary data from the store."""
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        cutoff = current_time.astimezone(UTC) - timedelta(
            seconds=self.cleanup_config.session_scenario_ttl_seconds
        )
        return self.store.delete_sessions_created_before(cutoff.isoformat())

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session(
        self,
        territory: str = "",
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> Session:
        """Create a persisted session state."""
        session_id = uuid4().hex
        now_timestamp = get_timestamp()
        session = Session(
            session_id=session_id,
            territory=territory,
            created=now_timestamp,
            updated=now_timestamp,
            owner_id=owner_id,
            metadata={} if metadata is None else metadata,
        )
        self.store.save_session(session.to_dict())
        return session

    def read_session(self, session_id: str) -> Session:
        """Return a persisted session state."""
        session_data = self._load_active_session_data(session_id)
        session = Session.from_dict(session_data)
        session.scenarios = {
            scenario.scenario_id: scenario
            for scenario in (
                Scenario.from_dict(scenario_data)
                for scenario_data in self.store.load_scenarios(session_id=session_id)
            )
        }
        session.evaluations = {
            evaluation.scenario_id: evaluation
            for evaluation in (
                Evaluation.from_dict(evaluation_data)
                for evaluation_data in self.store.load_evaluations_for_session(
                    session_id
                )
            )
        }
        return session

    def list_sessions(self) -> list[Session]:
        """Return all persisted sessions."""
        sessions = []
        for session_data in self.store.load_sessions():
            if self._is_expired(session_data):
                continue
            session = Session.from_dict(session_data)
            session.scenarios = {}
            session.evaluations = {}
            sessions.append(session)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """Delete a persisted session and all its drafts/evaluations."""
        self.store.delete_session(session_id)
