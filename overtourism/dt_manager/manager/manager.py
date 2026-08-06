# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from civic_digital_twins.dt_model.model import Model
from civic_digital_twins.dt_model.simulation.runner import ModelEvaluator

from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.relationship.manager import RelationshipManager
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.session.manager import SessionManager
from overtourism.dt_manager.stores.builder import create_store
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from overtourism.dt_manager.utils.metadata import ExtrasConfig

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.simulation.runner import ModelOutput

    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.problem.problem import Problem
    from overtourism.dt_manager.proposal.proposal import Proposal
    from overtourism.dt_manager.scenario.scenario import Scenario


class Manager:
    """
    Coordinator exposing problem, scenario, proposal, and relationship manager.
    """

    def __init__(
        self,
        model: Model,
        model_evaluator: ModelEvaluator,
        store_config: StoreConfig,
        extras_config: ExtrasConfig | None = None,
        names_cfg: BaseConfig | None = None,
    ) -> None:
        """Create the high-level manager facade."""
        self.store = create_store(store_config.store_type, **store_config.config)
        self.name_cfg = names_cfg if names_cfg is not None else BaseConfig()
        self.problem_manager = ProblemManager(self.store)
        self.proposal_manager = ProposalManager(self.store)
        self.scenario_manager = ScenarioManager(
            self.name_cfg.scenario_id,
            model,
            model_evaluator,
            self.store,
        )
        self.evaluation_manager = EvaluationManager(
            self.store,
            Executor(model, model_evaluator),
        )
        self.relationship_manager = RelationshipManager(self.store)
        self.session_manager = SessionManager()

        self.extras_config = (
            extras_config if extras_config is not None else ExtrasConfig()
        )

        self._setup()

    # ───────────────────────────────────────────────────────────
    # Setup
    # ───────────────────────────────────────────────────────────

    def _setup(self) -> None:
        """
        Bootstrap the default problem when the store is empty.
        """
        try:
            self.scenario_manager.read_scenario(self.name_cfg.scenario_id)
            return
        except EntityDoesNotExist:
            pass

        self.problem_manager.create_problem(
            problem_id=self.name_cfg.problem_id,
            tenant=self.name_cfg.tenant,
            name=self.name_cfg.problem_name,
            description=self.name_cfg.problem_description,
            extras=self.name_cfg.problem_extras,
        )
        self.scenario_manager.create_scenario(
            scenario_id=self.name_cfg.scenario_id,
            tenant=self.name_cfg.tenant,
            name=self.name_cfg.scenario_name,
            description=self.name_cfg.scenario_description,
            extras=self.name_cfg.scenario_extras,
        )
        self.evaluate_scenario(scenario_id=self.name_cfg.scenario_id)
        self.proposal_manager.create_proposal(
            proposal_id=self.name_cfg.proposal_id,
            problem_id=self.name_cfg.problem_id,
            name=self.name_cfg.proposal_name,
            description=self.name_cfg.proposal_description,
            status=self.name_cfg.proposal_status,
            extras=self.name_cfg.proposal_extras,
        )
        self.relationship_manager.link_scenario_proposal(
            proposal_id=self.name_cfg.proposal_id,
            scenario_id=self.name_cfg.scenario_id,
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
        """Create a problem."""
        return self.problem_manager.create_problem(
            uuid4().hex,
            tenant=tenant,
            name=name,
            description=description,
            extras=extras,
        )

    def read_problem(self, problem_id: str) -> Problem:
        """Return a problem."""
        return self.problem_manager.read_problem(problem_id)

    def list_problems(self) -> list[Problem]:
        """Return all problems."""
        return self.problem_manager.list_problems()

    def update_problem(self, problem_id: str, **kwargs) -> Problem:
        """Update a problem's attributes."""
        return self.problem_manager.update_problem(problem_id, **kwargs)

    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem and clear its child manager."""
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
        """Create a proposal and persist any requested scenario links."""
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
        """Return a proposal."""
        return self.proposal_manager.read_proposal(proposal_id)

    def list_proposals(
        self,
        problem_id: str | None = None,
        scenario_id: str | None = None,
    ) -> list[Proposal]:
        """Return all proposals."""
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
        """Update a proposal and persist any requested scenario links."""
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
        """Delete a proposal and persist the resulting aggregate."""
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
        """Create a scenario and persist it."""
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
        """Return all stored scenarios for a problem."""
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
        """Update a scenario's attributes."""
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
        """Delete a scenario and persist the resulting aggregate."""
        self.scenario_manager.delete_scenario(scenario_id)
        self.evaluation_manager.delete_evaluations_for_scenario(scenario_id)

    def scenario_extras_from_dict(self, scenario_dict: dict) -> dict:
        """Extract scenario extras from a dictionary."""
        return self.extras_config.scenario_extras_from_dict(scenario_dict)

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def evaluate_scenario(
        self,
        scenario_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ) -> Evaluation:
        """Evaluate a stored scenario and persist the evaluation state."""
        try:
            scenario = self.scenario_manager.read_scenario(scenario_id)
        except EntityDoesNotExist:
            scenario = self.scenario_manager.create_scenario(scenario_id)

        evaluation = self.evaluation_manager.create_evaluation(
            uuid4().hex,
            scenario.scenario_id,
        )
        return self.evaluation_manager.run_evaluation(
            evaluation.evaluation_id,
            scenario,
            ensemble_size=ensemble_size,
            **kwargs,
        )

    def read_scenario_data(self, scenario_id: str) -> ModelOutput:
        """Return the latest stored evaluation result for a scenario.

        If no evaluation exists yet, create one on demand and return its result.
        """
        try:
            result = self.evaluation_manager.read_latest_evaluation(scenario_id).result
        except EntityDoesNotExist:
            return self.evaluate_scenario(scenario_id).result

        if hasattr(result, "to_snapshot"):
            return result
        if isinstance(result, dict):
            try:
                return self.model_evaluator.build_output(result)
            except (AttributeError, KeyError, TypeError, ValueError):
                return self.evaluate_scenario(scenario_id).result
        return self.evaluate_scenario(scenario_id).result

    def read_evaluation(self, evaluation_id: str) -> Evaluation:
        """Return a stored evaluation by identifier."""
        return self.evaluation_manager.read_evaluation(evaluation_id)

    def list_evaluations(
        self,
        scenario_id: str | None = None,
    ) -> list[Evaluation]:
        """Return stored evaluations for a scenario."""
        return self.evaluation_manager.list_evaluations(scenario_id)

    def read_latest_evaluation(self, scenario_id: str) -> Evaluation:
        """Return the latest evaluation for a scenario."""
        return self.evaluation_manager.read_latest_evaluation(scenario_id)

    def update_evaluation(
        self,
        evaluation_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ) -> Evaluation:
        """Re-run a stored evaluation for its current scenario."""
        evaluation = self.read_evaluation(evaluation_id)
        scenario = self.read_scenario(evaluation.scenario_id)
        return self.evaluation_manager.rerun_evaluation(
            evaluation_id,
            scenario,
            ensemble_size=ensemble_size,
            **kwargs,
        )

    def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete a stored evaluation by identifier."""
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
        """Create a session and return its identifier."""
        return self.session_manager.create_session(metadata)

    def read_session(self, session_id: str) -> dict:
        """Return a session's metadata."""
        return self.session_manager.read_session(session_id)

    def list_sessions(self) -> list[dict]:
        """Return all sessions' metadata."""
        return self.session_manager.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its related scenarios and evaluations."""
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
        """Promote a transient session scenario to persistent storage."""
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
        except (EntityDoesNotExist, KeyError):
            pass
        self.session_manager.delete_session(session_id)
        return self.read_scenario(scenario_id)

    def read_session_scenario(self, session_id: str, scenario_id: str) -> Scenario:
        """Return an in-memory session scenario."""
        return self.session_manager.read_session_scenario(session_id, scenario_id)

    def list_session_scenarios(self, session_id: str) -> list[Scenario]:
        """Return all in-memory session scenarios."""
        return self.session_manager.list_session_scenarios(session_id)

    def delete_session_scenario(self, session_id: str, scenario_id: str) -> None:
        """Delete a transient session scenario."""
        self.session_manager.delete_session_scenario(session_id, scenario_id)

    # ───────────────────────────────────────────────────────────
    # Session Evaluations
    # ───────────────────────────────────────────────────────────

    def create_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
        **kwargs,
    ) -> Evaluation:
        """Evaluate an existing transient session scenario."""
        scenario = self.session_manager.read_session_scenario(session_id, scenario_id)
        evaluation_id = uuid4().hex
        evaluation = self.evaluation_manager.build_running_evaluation(
            evaluation_id,
            scenario_id=scenario_id,
        )
        evaluation = self.evaluation_manager.execute_evaluation(
            evaluation,
            scenario,
            **kwargs,
        )
        self.session_manager.create_session_evaluation(
            session_id,
            scenario_id,
            evaluation,
        )
        return evaluation

    def read_session_evaluation(
        self,
        session_id: str,
        scenario_id: str,
    ) -> Evaluation:
        """Return an in-memory session evaluation."""
        return self.session_manager.read_session_evaluation(
            session_id,
            scenario_id,
        )

    def read_session_evaluation_by_id(
        self,
        session_id: str,
        evaluation_id: str,
    ) -> Evaluation:
        """Return an in-memory session evaluation by identifier."""
        return self.session_manager.read_session_evaluations_by_id(
            session_id,
            evaluation_id,
        )
