# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from overtourism.dt_manager.session.session import SessionState
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.scenario.scenario import Scenario


class SessionManager:
    """Own transient session state and the draft/evaluation workflow."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session(
        self,
        metadata: dict | None = None,
    ) -> SessionState:
        """Create an in-memory session state."""
        session_id = uuid4().hex
        now_timestamp = get_timestamp()
        session = SessionState(
            session_id=session_id,
            created=now_timestamp,
            updated=now_timestamp,
            metadata={} if metadata is None else metadata,
        )
        self.sessions[session_id] = session
        return session

    def read_session(self, session_id: str) -> SessionState:
        """Return an in-memory session state."""
        return self.sessions[session_id]

    def list_sessions(self) -> list[SessionState]:
        """Return all in-memory sessions."""
        return list(self.sessions.values())

    def delete_session(self, session_id: str) -> None:
        """Delete an in-memory session and all its drafts/evaluations."""
        self.sessions.pop(session_id, None)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(self, session_id: str, scenario: Scenario) -> Scenario:
        """Create a transient scenario for a session."""
        session = self.sessions[session_id]
        session.scenarios[scenario.scenario_id] = scenario
        session.active_scenario_id = scenario.scenario_id
        session.evaluations.pop(scenario.scenario_id, None)
        session.updated = get_timestamp()
        return scenario

    def read_session_scenario(self, session_id: str, scenario_id: str) -> Scenario:
        """Return a transient scenario for a session."""
        return self.sessions[session_id].scenarios[scenario_id]

    def list_session_scenarios(self, session_id: str) -> list[Scenario]:
        """Return all drafts stored in a session."""
        return list(self.sessions[session_id].scenarios.values())

    def delete_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
    ) -> None:
        """Delete a draft scenario and its evaluation from a session."""
        self.sessions[session_id].scenarios.pop(scenario_id, None)
        self.sessions[session_id].evaluations.pop(scenario_id, None)
        self.sessions[session_id].active_scenario_id = next(
            iter(self.sessions[session_id].scenarios), None
        )
        self.sessions[session_id].updated = get_timestamp()

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def create_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
        evaluation: Evaluation,
    ) -> Evaluation:
        """Evaluate an existing transient session scenario."""
        session = self.sessions[session_id]
        if scenario_id not in session.scenarios:
            raise EntityDoesNotExist(
                f"Scenario '{scenario_id}' does not exist in session '{session_id}'"
            )
        session.evaluations[scenario_id] = evaluation
        session.active_scenario_id = scenario_id
        session.updated = get_timestamp()
        return evaluation

    def read_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
    ) -> Evaluation:
        """Return an in-memory evaluation by identifier."""
        return self.sessions[session_id].evaluations[scenario_id]

    def read_session_evaluations_by_id(
        self,
        session_id: str,
        evaluation_id: str,
    ) -> Evaluation:
        """Return an in-memory evaluation by identifier."""
        for evaluation in self.sessions[session_id].evaluations.values():
            if evaluation.evaluation_id == evaluation_id:
                return evaluation
        raise EntityDoesNotExist(
            f"Evaluation '{evaluation_id}' does not exist in session '{session_id}'"
        )

    def delete_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
    ) -> None:
        """Delete an in-memory evaluation by identifier."""
        self.sessions[session_id].evaluations.pop(scenario_id, None)
