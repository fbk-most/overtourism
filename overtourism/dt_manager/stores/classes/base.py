# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod


class Store(ABC):
    """Abstract base for problem, scenario, and proposal persistence."""

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_session(self, session_data: dict) -> None:
        """Persist a session document."""

    @abstractmethod
    def load_session(self, session_id: str) -> dict:
        """Load a single session."""

    @abstractmethod
    def load_sessions(
        self,
        tenant: str | None = None,
        owner_id: str | None = None,
    ) -> list[dict]:
        """Load all sessions."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete a session document."""

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_problem(self, problem_data: dict) -> None:
        """Persist a problem document."""

    @abstractmethod
    def load_problem(self, problem_id: str) -> dict:
        """Load a problem document."""

    @abstractmethod
    def load_problems(self, tenant: str | None = None) -> list[dict]:
        """Load all problems."""

    @abstractmethod
    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem document."""

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_proposal(self, proposal_data: dict) -> None:
        """Persist a proposal document."""

    @abstractmethod
    def load_proposal(self, proposal_id: str) -> dict:
        """Load a single proposal."""

    @abstractmethod
    def load_proposals(
        self,
        problem_id: str | None = None,
        scenario_id: str | None = None,
    ) -> list[dict]:
        """Load all proposals for a problem."""

    @abstractmethod
    def delete_proposal(self, proposal_id: str) -> None:
        """Delete a proposal document."""

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_scenario(self, scenario_data: dict) -> None:
        """Persist a scenario document."""

    @abstractmethod
    def load_scenario(self, scenario_id: str) -> dict:
        """Load a single scenario."""

    @abstractmethod
    def load_scenarios(
        self,
        tenant: str | None = None,
        proposal_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Load all scenarios for a tenant."""

    @abstractmethod
    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a scenario document."""

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_relationships(self, relationships: list[dict[str, str]]) -> None:
        """Persist proposal-scenario relationships."""

    @abstractmethod
    def load_relationships(self) -> list[dict[str, str]]:
        """Load all proposal-scenario relationships."""

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_evaluation(self, evaluation_data: dict) -> None:
        """Persist an evaluation document."""

    @abstractmethod
    def load_evaluation(self, evaluation_id: str) -> dict:
        """Load a single evaluation."""

    @abstractmethod
    def load_evaluations(self, scenario_id: str | None = None) -> list[dict]:
        """Load all evaluations for a scenario."""

    @abstractmethod
    def load_evaluations_for_session(
        self,
        session_id: str,
    ) -> list[dict]:
        """Load all evaluations for a session."""

    @abstractmethod
    def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete an evaluation document."""
