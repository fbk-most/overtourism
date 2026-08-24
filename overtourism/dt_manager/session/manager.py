# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from uuid import uuid4

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.session.session import SessionState
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
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
    ) -> SessionState:
        """Create a persisted session state."""
        session_id = uuid4().hex
        now_timestamp = get_timestamp()
        session = SessionState(
            session_id=session_id,
            tenant=tenant,
            created=now_timestamp,
            updated=now_timestamp,
            owner_id=owner_id,
            metadata={} if metadata is None else metadata,
        )
        self.store.save_session(session.to_dict())
        return session

    def read_session(self, session_id: str) -> SessionState:
        """Return a persisted session state."""
        session_data = self.store.load_session(session_id)
        session = SessionState.from_dict(session_data)
        session.scenarios = {
            scenario.scenario_id: scenario
            for scenario in self.list_session_scenarios(session_id)
        }
        session.evaluations = {
            evaluation.scenario_id: evaluation
            for evaluation in self.list_session_evaluations(session_id)
        }
        return session

    def list_sessions(self) -> list[SessionState]:
        """Return all persisted sessions."""
        sessions = []
        for session_data in self.store.load_sessions():
            session = SessionState.from_dict(session_data)
            session.scenarios = {}
            session.evaluations = {}
            sessions.append(session)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """Delete a persisted session and all its drafts/evaluations."""
        self.store.delete_session(session_id)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(self, session_id: str, scenario: Scenario) -> Scenario:
        """Create and persist a scenario for a session."""
        session = self.read_session(session_id)
        scenario.session_id = session_id
        scenario.updated = get_timestamp()
        self.store.save_scenario(scenario.to_dict())
        session.active_scenario_id = scenario.scenario_id
        session.updated = get_timestamp()
        self.store.save_session(session.to_dict())
        return scenario

    def read_session_scenario(self, session_id: str, scenario_id: str) -> Scenario:
        """Return a persisted scenario for a session."""
        scenario = Scenario.from_dict(self.store.load_scenario(scenario_id))
        if scenario.session_id != session_id:
            raise EntityDoesNotExist(
                f"Scenario '{scenario_id}' does not exist in session '{session_id}'"
            )
        return scenario

    def list_session_scenarios(self, session_id: str) -> list[Scenario]:
        """Return all persisted scenarios stored in a session."""
        return [
            Scenario.from_dict(scenario_data)
            for scenario_data in self.store.load_scenarios(session_id=session_id)
        ]

    def delete_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
    ) -> None:
        """Delete a persisted session scenario and its evaluation."""
        self.read_session_scenario(session_id, scenario_id)
        self.store.delete_scenario(scenario_id)
        session = self.read_session(session_id)
        remaining_scenarios = self.list_session_scenarios(session_id)
        session.active_scenario_id = next(
            (scenario.scenario_id for scenario in remaining_scenarios),
            None,
        )
        session.updated = get_timestamp()
        self.store.save_session(session.to_dict())

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def create_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
        evaluation: Evaluation,
    ) -> Evaluation:
        """Evaluate and persist an existing session scenario."""
        scenario = self.read_session_scenario(session_id, scenario_id)
        if scenario.session_id != session_id:
            raise EntityDoesNotExist(
                f"Scenario '{scenario_id}' does not exist in session '{session_id}'"
            )
        evaluation.session_id = session_id
        evaluation.started = evaluation.started or get_timestamp()
        evaluation.version += 1
        self.store.save_evaluation(evaluation.to_dict())
        session = self.read_session(session_id)
        session.active_scenario_id = scenario_id
        session.updated = get_timestamp()
        self.store.save_session(session.to_dict())
        return evaluation

    def read_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
    ) -> Evaluation:
        """Return a persisted evaluation by scenario identifier."""
        for evaluation in self.list_session_evaluations(session_id):
            if evaluation.scenario_id == scenario_id:
                return evaluation
        raise EntityDoesNotExist(
            f"Evaluation for scenario '{scenario_id}' does not exist in session '{session_id}'"
        )

    def read_session_evaluations_by_id(
        self,
        session_id: str,
        evaluation_id: str,
    ) -> Evaluation:
        """Return a persisted evaluation by identifier."""
        for evaluation in self.list_session_evaluations(session_id):
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
        """Delete a persisted evaluation by scenario identifier."""
        evaluation = self.read_session_evaluation(session_id, scenario_id)
        self.store.delete_evaluation(evaluation.evaluation_id)

    def list_session_evaluations(self, session_id: str) -> list[Evaluation]:
        """Return all persisted evaluations stored in a session."""
        return [
            Evaluation.from_dict(evaluation_data)
            for evaluation_data in self.store.load_evaluations_for_session(session_id)
        ]
