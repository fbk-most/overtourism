# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from uuid import uuid4

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.session.session import Session
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.utils import get_timestamp


class SessionManager:
    """Persist session state and the draft/evaluation workflow."""

    def __init__(self, store: Store) -> None:
        self.store = store

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session(
        self,
        tenant: str = "",
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> Session:
        """Create a persisted session state."""
        session_id = uuid4().hex
        now_timestamp = get_timestamp()
        session = Session(
            session_id=session_id,
            tenant=tenant,
            created=now_timestamp,
            updated=now_timestamp,
            owner_id=owner_id,
            metadata={} if metadata is None else metadata,
        )
        self.store.save_session(session.to_dict())
        return session

    def read_session(self, session_id: str) -> Session:
        """Return a persisted session state."""
        session_data = self.store.load_session(session_id)
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
            session = Session.from_dict(session_data)
            session.scenarios = {}
            session.evaluations = {}
            sessions.append(session)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """Delete a persisted session and all its drafts/evaluations."""
        self.store.delete_session(session_id)
