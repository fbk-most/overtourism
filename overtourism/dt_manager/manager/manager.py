# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from uuid import uuid4

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
)
from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.relationship.manager import RelationshipManager
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.session.manager import SessionManager
from overtourism.dt_manager.stores.builder import create_store
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.metadata import ExtrasConfig


class Manager:
    """CRUD manager for problems, proposals, scenarios, evaluations, and sessions."""

    def __init__(
        self,
        store_config: StoreConfig,
        extras_config: ExtrasConfig | None = None,
        names_cfg: BaseConfig | None = None,
    ) -> None:
        self.store = create_store(store_config.store_type, **store_config.config)
        self.name_cfg = names_cfg if names_cfg is not None else BaseConfig()
        self.problem_manager = ProblemManager(self.store)
        self.proposal_manager = ProposalManager(self.store)
        self.scenario_manager = ScenarioManager(self.name_cfg.scenario_id, self.store)
        self.evaluation_manager = EvaluationManager(self.store)
        self.relationship_manager = RelationshipManager(self.store)
        self.session_manager = SessionManager()
        self.extras_config = (
            extras_config if extras_config is not None else ExtrasConfig()
        )

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def create_problem(
        self,
        tenant: str,
        *,
        name: str,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Problem:
        """Create and persist a new problem."""
        return self.problem_manager.create_problem(
            uuid4().hex,
            tenant=tenant,
            name=name,
            description=description,
            extras=extras,
        )

    def read_problem(self, problem_id: str) -> Problem:
        """Return a stored problem."""
        return self.problem_manager.read_problem(problem_id)

    def list_problems(self) -> list[Problem]:
        """Return all stored problems."""
        return self.problem_manager.list_problems()

    def update_problem(self, problem_id: str, **kwargs) -> Problem:
        """Update a stored problem."""
        return self.problem_manager.update_problem(problem_id, **kwargs)

    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem and its proposals."""
        self.problem_manager.delete_problem(problem_id)
        for proposal in self.proposal_manager.list_proposals():
            if proposal.problem_id == problem_id:
                self.proposal_manager.delete_proposal(proposal.proposal_id)

    def problem_extras_from_dict(self, problem_dict: dict) -> dict:
        """Extract problem extras from a dictionary."""
        return self.extras_config.problem_extras_from_dict(problem_dict)

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def create_proposal(
        self,
        problem_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        extras: dict | None = None,
        related_scenario_ids: list[str] | None = None,
    ) -> Proposal:
        """Create and persist a new proposal."""
        proposal = self.proposal_manager.create_proposal(
            proposal_id=uuid4().hex,
            problem_id=problem_id,
            name=name,
            description=description,
            status=status,
            extras=extras,
        )
        if related_scenario_ids is not None:
            self.relationship_manager.set_related_scenario_ids(
                proposal_id=proposal.proposal_id,
                scenario_ids=related_scenario_ids,
            )
        return proposal

    def read_proposal(self, proposal_id: str) -> Proposal:
        """Return a stored proposal."""
        return self.proposal_manager.read_proposal(proposal_id)

    def list_proposals(
        self,
        problem_id: str | None = None,
        scenario_id: str | None = None,
    ) -> list[Proposal]:
        """Return stored proposals filtered by problem or scenario."""
        return self.proposal_manager.list_proposals(problem_id, scenario_id)

    def update_proposal(
        self,
        proposal_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        extras: dict | None = None,
        related_scenario_ids: list[str] | None = None,
    ) -> Proposal:
        """Update a stored proposal and its links."""
        proposal = self.proposal_manager.update_proposal(
            proposal_id=proposal_id,
            name=name,
            description=description,
            status=status,
            extras=extras,
        )
        if related_scenario_ids is not None:
            self.relationship_manager.set_related_scenario_ids(
                proposal_id=proposal_id,
                scenario_ids=related_scenario_ids,
            )
        return proposal

    def delete_proposal(self, proposal_id: str) -> None:
        """Delete a stored proposal."""
        self.proposal_manager.delete_proposal(proposal_id)

    def proposal_extras_from_dict(self, proposal_dict: dict) -> dict:
        """Extract proposal extras from a dictionary."""
        return self.extras_config.proposal_extras_from_dict(proposal_dict)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def create_scenario(
        self,
        *,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        proposal_id: str | None = None,
    ) -> Scenario:
        """Create and persist a new scenario."""
        scenario = self.scenario_manager.create_scenario(
            scenario_id=uuid4().hex,
            tenant=self.name_cfg.tenant,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        if proposal_id is not None:
            self.relationship_manager.link_scenario_proposal(
                proposal_id=proposal_id,
                scenario_id=scenario.scenario_id,
            )
        return scenario

    def read_scenario(self, scenario_id: str) -> Scenario:
        """Return a stored scenario."""
        return self.scenario_manager.read_scenario(scenario_id)

    def list_scenarios(
        self,
        tenant: str | None = None,
        proposal_id: str | None = None,
    ) -> list[Scenario]:
        """Return stored scenarios filtered by tenant or proposal."""
        return self.scenario_manager.list_scenarios(
            tenant=tenant,
            proposal_id=proposal_id,
        )

    def update_scenario(
        self,
        scenario_id: str,
        *,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a stored scenario."""
        scenario = self.scenario_manager.update_scenario(
            scenario_id=scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        # For the moment we choose to delete all evaluations when a scenario is updated
        self.evaluation_manager.delete_evaluations_for_scenario(scenario_id)
        return scenario

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a scenario and its evaluations."""
        self.scenario_manager.delete_scenario(scenario_id)
        self.evaluation_manager.delete_evaluations_for_scenario(scenario_id)

    def scenario_extras_from_dict(self, scenario_dict: dict) -> dict:
        """Extract scenario extras from a dictionary."""
        return self.extras_config.scenario_extras_from_dict(scenario_dict)

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def read_evaluation(self, evaluation_id: str) -> Evaluation:
        """Return a stored evaluation."""
        return self.evaluation_manager.read_evaluation(evaluation_id)

    def read_evaluation_data(self, evaluation_id: str):
        """Return the stored result payload for an evaluation."""
        return self.read_evaluation(evaluation_id).result

    def create_evaluation(
        self,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        *,
        started: str | None = None,
    ) -> Evaluation:
        """Create and persist a new evaluation with an internal ID."""
        return self.evaluation_manager.create_evaluation(
            uuid4().hex,
            scenario_id,
            type=type,
            started=started,
        )

    def build_running_evaluation(
        self,
        evaluation_id: str,
        *,
        scenario_id: str,
        type: str = DEFAULT_EVALUATION_TYPE,
        started: str | None = None,
    ) -> Evaluation:
        """Build a running evaluation object without persisting it."""
        return self.evaluation_manager.build_running_evaluation(
            evaluation_id,
            scenario_id=scenario_id,
            type=type,
            started=started,
        )

    def save_evaluation(self, evaluation: Evaluation) -> None:
        """Persist an evaluation."""
        self.evaluation_manager.save_evaluation(evaluation)

    def list_evaluations(self, scenario_id: str | None = None) -> list[Evaluation]:
        """Return stored evaluations, optionally filtered by scenario."""
        return self.evaluation_manager.list_evaluations(scenario_id)

    def read_latest_evaluation(self, scenario_id: str) -> Evaluation:
        """Return the most recent evaluation for a scenario."""
        return self.evaluation_manager.read_latest_evaluation(scenario_id)

    def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete a stored evaluation."""
        self.evaluation_manager.delete_evaluation(evaluation_id)

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    def link_scenario_to_proposal(
        self,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal."""
        self.relationship_manager.link_scenario_proposal(proposal_id, scenario_id)

    def unlink_scenario_from_proposal(self, proposal_id: str, scenario_id: str) -> None:
        """Remove a stored link between a scenario and a proposal."""
        self.relationship_manager.unlink_scenario_proposal(proposal_id, scenario_id)

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session(self, metadata: dict | None = None) -> str:
        """Create an in-memory session."""
        return self.session_manager.create_session(metadata)

    def create_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
        evaluation: Evaluation,
    ) -> Evaluation:
        """Attach an evaluation to an in-memory session."""
        return self.session_manager.create_session_evaluation(
            session_id,
            scenario_id,
            evaluation,
        )

    def read_session(self, session_id: str) -> dict:
        """Return an in-memory session."""
        return self.session_manager.read_session(session_id)

    def list_sessions(self) -> list[dict]:
        """Return all in-memory sessions."""
        return self.session_manager.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """Delete an in-memory session."""
        self.session_manager.delete_session(session_id)

    # ───────────────────────────────────────────────────────────
    # Session Scenarios
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
    ) -> Scenario:
        """Create a transient scenario for a session."""
        scenario = self.scenario_manager.detach_scenario(scenario_id, values)
        return self.session_manager.create_session_scenario(session_id, scenario)

    def save_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        proposal_id: str | None = None,
    ) -> Scenario:
        """Persist a transient scenario back into the store."""
        session_scenario = self.session_manager.read_session_scenario(
            session_id,
            scenario_id,
        )
        if name is not None:
            session_scenario.name = name
        if description is not None:
            session_scenario.description = description
        if extras is not None:
            session_scenario.extras = session_scenario.extras.update(extras)

        self.store.save_scenario(session_scenario.to_dict())

        if proposal_id is not None:
            self.relationship_manager.link_scenario_proposal(
                proposal_id=proposal_id,
                scenario_id=session_scenario.scenario_id,
            )
        try:
            evaluations = self.session_manager.read_session_evaluation(
                session_id,
                session_scenario.scenario_id,
            )
            self.evaluation_manager.save_evaluation(evaluations)
        except Exception:
            pass
        self.session_manager.delete_session(session_id)
        return self.read_scenario(scenario_id)

    def read_session_scenario(self, session_id: str, scenario_id: str) -> Scenario:
        """Return a transient scenario for a session."""
        return self.session_manager.read_session_scenario(session_id, scenario_id)

    def list_session_scenarios(self, session_id: str) -> list[Scenario]:
        """Return all transient scenarios for a session."""
        return self.session_manager.list_session_scenarios(session_id)

    def delete_session_scenario(self, session_id: str, scenario_id: str) -> None:
        """Delete a transient session scenario."""
        self.session_manager.delete_session_scenario(session_id, scenario_id)

    def read_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
    ) -> Evaluation:
        """Return a transient session evaluation."""
        return self.session_manager.read_session_evaluation(
            session_id,
            scenario_id,
        )

    def read_session_evaluation_by_id(
        self,
        session_id: str,
        evaluation_id: str,
    ) -> Evaluation:
        """Return a transient session evaluation by evaluation identifier."""
        return self.session_manager.read_session_evaluations_by_id(
            session_id,
            evaluation_id,
        )
