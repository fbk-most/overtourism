# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from civic_digital_twins.dt_model.model import Model

from overtourism.dt_manager.classes.metadata import ExtrasConfig
from overtourism.dt_manager.classes.model import ModelEvaluator
from overtourism.dt_manager.evaluation.evaluation import DEFAULT_EVALUATION_TYPE
from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.stores.builder import create_store
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.exception import ScenarioDoesNotExist

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.classes.model import ModelOutput
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.problem.problem import Problem
    from overtourism.dt_manager.proposal.proposal import Proposal
    from overtourism.dt_manager.scenario.scenario import Scenario


class Manager:
    """
    Coordinator exposing problem, scenario, proposal, and relationship managers.
    """

    def __init__(
        self,
        model: Model,
        model_evaluator: ModelEvaluator,
        store_config: StoreConfig,
        extras_config: ExtrasConfig | None = None,
        base_problem_config: BaseConfig | None = None,
    ) -> None:
        """Create the high-level manager facade."""
        self.model = model
        self.model_evaluator = model_evaluator
        self.extras_config = (
            extras_config if extras_config is not None else ExtrasConfig()
        )
        self.base_problem_config = (
            base_problem_config if base_problem_config is not None else BaseConfig()
        )

        self.store = create_store(store_config.store_type, **store_config.config)

        self.problem_manager = ProblemManager(self.store)
        self.scenario_managers: dict[str, ScenarioManager] = {}
        self.evaluation_managers: dict[str, EvaluationManager] = {}
        self.executor = Executor(self.model, self.model_evaluator)
        self.proposal_managers: dict[str, ProposalManager] = {}

        self._setup()

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _setup(self) -> None:
        """
        Initialize the manager.
        Bootstrap the default problem when the store is empty,
        then load all problems.
        """
        problems = self.store.load_problems()

        if not problems:
            self._bootstrap_default_problem()
            problem_ids = [self.base_problem_config.problem_id]
        else:
            problem_ids = [problem["problem_id"] for problem in problems]

        for problem_id in problem_ids:
            self.problem_manager.read_problem(problem_id)
            self._init_problem_managers(problem_id)

    def _bootstrap_default_problem(self) -> None:
        """Create the default problem graph when the store is empty."""
        self.problem_manager.create_problem(
            self.base_problem_config.problem_id,
            tenant=self.base_problem_config.tenant,
            name=self.base_problem_config.problem_name,
            description=self.base_problem_config.problem_description,
            extras=self.base_problem_config.problem_extras,
        )
        self._init_problem_managers(self.base_problem_config.problem_id)
        self.scenario_managers[self.base_problem_config.problem_id].create_scenario(
            scenario_id=self.base_problem_config.scenario_id,
            name=self.base_problem_config.scenario_name,
            description=self.base_problem_config.scenario_description,
            extras=self.base_problem_config.scenario_extras,
        )
        self.proposal_managers[self.base_problem_config.problem_id].create_proposal(
            proposal_id=self.base_problem_config.proposal_id,
            name=self.base_problem_config.proposal_name,
            description=self.base_problem_config.proposal_description,
            status=self.base_problem_config.proposal_status,
            extras=self.base_problem_config.proposal_extras,
        )
        self.problem_manager.link_scenario_to_proposal(
            self.base_problem_config.problem_id,
            self.base_problem_config.proposal_id,
            self.base_problem_config.scenario_id,
        )
        self.evaluate_scenario(
            self.base_problem_config.problem_id,
            self.base_problem_config.scenario_id,
        )

    def _init_problem_managers(self, problem_id: str) -> None:
        """Create the child managers associated with a problem."""
        self.evaluation_managers[problem_id] = EvaluationManager(
            self.store,
            problem_id,
            self.executor,
        )
        self.scenario_managers[problem_id] = ScenarioManager(
            problem_id,
            self.model,
            self.model_evaluator,
            self.store,
        )
        self.proposal_managers[problem_id] = ProposalManager(problem_id, self.store)

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def create_problem(
        self,
        problem_id: str,
        *,
        problem_kwargs: dict,
    ) -> None:
        """Create a problem together with its default scenario."""

        # Creaate problem
        self.problem_manager.create_problem(problem_id, **problem_kwargs)
        self._init_problem_managers(problem_id)

        # Create always default scenario
        self.scenario_managers[problem_id].create_scenario(
            scenario_id=self.base_problem_config.scenario_id,
            name=self.base_problem_config.scenario_name,
            description=self.base_problem_config.scenario_description,
            extras=self.base_problem_config.scenario_extras,
        )

        self.evaluate_scenario(problem_id, self.base_problem_config.scenario_id)

    def read_problem(self, problem_id: str) -> Problem:
        """Return a problem."""
        return self.problem_manager.read_problem(problem_id)

    def list_problems(self) -> list[Problem]:
        """Return all problems."""
        return self.problem_manager.list_problems()

    def update_problem(self, problem_id: str, **kwargs) -> None:
        """Update a problem's attributes."""
        self.problem_manager.update_problem(problem_id, **kwargs)

    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem and clear its child managers."""
        self.problem_manager.delete_problem(problem_id)
        self.evaluation_managers.pop(problem_id, None)
        self.scenario_managers.pop(problem_id, None)
        self.proposal_managers.pop(problem_id, None)

    def problem_extras_from_dict(self, problem_dict: dict) -> dict:
        """Extract problem extras from a dictionary."""
        return self.extras_config.problem_extras_from_dict(problem_dict)

    def link_scenario_to_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal."""
        self.problem_manager.link_scenario_to_proposal(
            problem_id,
            proposal_id,
            scenario_id,
        )

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def create_scenario(
        self,
        problem_id: str,
        *,
        scenario_id: str,
        session_id: str,
        values: dict,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        proposal_id: str | None = None,
        ensemble_size: int = 20,
        **kwargs,
    ) -> Scenario:
        """Create a scenario, evaluate it, and persist the resulting graph."""

        # Generate a unique scenario ID
        new_id = f"{scenario_id}_{session_id}_{uuid4().hex}"

        # Create the scenario in memory
        scenario = self.scenario_managers[problem_id].create_scenario(
            scenario_id=new_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        self.evaluate_scenario(
            problem_id,
            scenario.scenario_id,
            ensemble_size=ensemble_size,
            **kwargs,
        )
        if proposal_id is not None:
            self.problem_manager.link_scenario_to_proposal(
                problem_id,
                proposal_id,
                scenario.scenario_id,
            )
        self.close_session(problem_id, session_id)
        return scenario

    def read_scenario(self, problem_id: str, scenario_id: str) -> Scenario:
        """Return a stored scenario."""
        return self.scenario_managers[problem_id].read_scenario(scenario_id)

    def list_scenarios(self, problem_id: str) -> list[Scenario]:
        """Return all stored scenarios for a problem."""
        return self.scenario_managers[problem_id].list_scenarios()

    def update_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> None:
        """Update a scenario's attributes."""
        self.scenario_managers[problem_id].update_scenario(
            scenario_id=scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        # For the moment we choose to delete all evaluations when a scenario is updated
        self.evaluation_managers[problem_id].delete_evaluations_for_scenario(
            scenario_id
        )

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        """Delete a scenario and persist the resulting aggregate."""
        self.scenario_managers[problem_id].delete_scenario(scenario_id)
        self.evaluation_managers[problem_id].delete_evaluations_for_scenario(
            scenario_id
        )
        self.problem_manager.unlink_scenario(problem_id, scenario_id)

    def scenario_extras_from_dict(self, scenario_dict: dict) -> dict:
        """Extract scenario extras from a dictionary."""
        return self.extras_config.scenario_extras_from_dict(scenario_dict)

    # ───────────────────────────────────────────────────────────
    # Session
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        *,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Create a transient scenario for a session."""
        return self.scenario_managers[problem_id].create_session_scenario(
            session_id,
            scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )

    def update_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a transient session scenario and invalidate its evaluation."""
        scenario = self.scenario_managers[problem_id].update_session_scenario(
            session_id,
            scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        self.evaluation_managers[problem_id].delete_session_evaluation(
            session_id,
            scenario_id,
        )
        return scenario

    def read_session_scenario(self, problem_id: str, session_id: str):
        """Return a transient scenario for a session."""
        return self.scenario_managers[problem_id].read_session_scenario(session_id)

    def read_session_evaluation(self, problem_id: str, session_id: str):
        """Return the transient evaluation attached to a session."""
        return self.evaluation_managers[problem_id].read_session_evaluation(session_id)

    def resume_session(
        self,
        problem_id: str,
        session_id: str,
    ) -> tuple[Scenario, Evaluation]:
        """Return the transient session scenario and its evaluation."""
        return (
            self.read_session_scenario(problem_id, session_id),
            self.read_session_evaluation(problem_id, session_id),
        )

    def save_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        *,
        scenario_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        proposal_id: str | None = None,
    ) -> Scenario:
        """Promote a transient session scenario to persistent storage."""
        scenario_manager = self.scenario_managers[problem_id]
        session_scenario = scenario_manager.read_session_scenario(session_id)
        if scenario_id is not None and session_scenario.scenario_id != scenario_id:
            raise ScenarioDoesNotExist(
                f"Scenario with ID {scenario_id} does not exist in session {session_id}"
            )

        if name is not None:
            session_scenario.name = name
        if description is not None:
            session_scenario.description = description
        if extras is not None:
            session_scenario.extras.update(extras)

        scenario_manager.save_session_scenario(session_id, scenario_id)

        self.evaluation_managers[problem_id].save_session_evaluation(session_id)

        if proposal_id is not None:
            self.problem_manager.link_scenario_to_proposal(
                problem_id,
                proposal_id,
                session_scenario.scenario_id,
            )

        self.close_session(problem_id, session_id)
        return session_scenario

    def close_session(self, problem_id: str, session_id: str) -> None:
        """Close a session and discard both scenario and evaluation state."""
        self.scenario_managers[problem_id].close_session(session_id)
        self.evaluation_managers[problem_id].close_session(session_id)

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def evaluate_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ):
        """Evaluate a stored scenario and persist the evaluation state."""
        scenario_manager = self.scenario_managers[problem_id]
        evaluation_manager = self.evaluation_managers[problem_id]
        try:
            scenario = scenario_manager.read_scenario(scenario_id)
        except Exception:
            scenario = scenario_manager.create_scenario(scenario_id)

        evaluation_id = f"{scenario.scenario_id}_{uuid4().hex}"
        evaluation_manager.create_evaluation(
            evaluation_id,
            scenario.scenario_id,
        )
        return evaluation_manager.run_evaluation(
            evaluation_id,
            scenario,
            ensemble_size=ensemble_size,
            **kwargs,
        )

    def evaluate_session(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        values: dict,
        ensemble_size: int = 20,
        **kwargs,
    ):
        """Evaluate a transient session scenario and keep both states in memory."""
        session_scenario = self.create_session_scenario(
            problem_id,
            session_id,
            scenario_id,
            values=values,
        )
        self.create_session_evaluation(
            problem_id,
            session_id,
            session_scenario.scenario_id,
            ensemble_size=ensemble_size,
            **kwargs,
        )
        return session_scenario

    def create_session_evaluation(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ) -> Evaluation:
        """Evaluate an existing transient session scenario."""
        scenario = self.read_session_scenario(problem_id, session_id)
        if scenario.scenario_id != scenario_id:
            raise ScenarioDoesNotExist(
                f"Scenario with ID {scenario_id} does not exist in session {session_id}"
            )
        evaluation_manager = self.evaluation_managers[problem_id]
        evaluation_manager.delete_session_evaluation(session_id)
        evaluation_id = f"{session_id}_{uuid4().hex}"
        evaluation_manager.create_session_evaluation(
            session_id=session_id,
            evaluation_id=evaluation_id,
            scenario_id=scenario.scenario_id,
            type=DEFAULT_EVALUATION_TYPE,
        )
        return evaluation_manager.run_session_evaluation(
            session_id,
            scenario,
            ensemble_size=ensemble_size,
            **kwargs,
        )

    def read_scenario_data(self, problem_id: str, scenario_id: str) -> ModelOutput:
        """Return the latest stored evaluation result for a scenario.

        If no evaluation exists yet, create one on demand and return its result.
        """
        try:
            result = (
                self.evaluation_managers[problem_id]
                .read_latest_evaluation(scenario_id)
                .result
            )
        except Exception:
            result = self.evaluate_scenario(problem_id, scenario_id).result
        return result

    def read_latest_evaluation(self, problem_id: str, scenario_id: str) -> Evaluation:
        """Return the latest evaluation for a scenario."""
        return self.evaluation_managers[problem_id].read_latest_evaluation(scenario_id)

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
        proposal_id: str | None = None,
    ) -> Proposal:
        """Create a proposal and persist any requested scenario links."""
        proposal_manager = self.proposal_managers[problem_id]
        if proposal_id is None:
            proposal_id = f"proposal_{len(proposal_manager.list_proposals())}"

        proposal = proposal_manager.create_proposal(
            proposal_id=proposal_id,
            name=name,
            description=description,
            status=status,
            extras=extras,
        )
        if related_scenario_ids is not None:
            self.problem_manager.set_related_scenario_ids(
                problem_id,
                proposal_id,
                related_scenario_ids,
            )
        return proposal

    def read_proposal(self, problem_id: str, proposal_id: str) -> Proposal:
        """Return a proposal."""
        return self.proposal_managers[problem_id].read_proposal(proposal_id)

    def list_proposals(self, problem_id: str) -> list[Proposal]:
        """Return all proposals for a problem."""
        return self.proposal_managers[problem_id].list_proposals()

    def update_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        extras: dict | None = None,
        related_scenario_ids: list[str] | None = None,
    ) -> None:
        """Update a proposal and persist any requested scenario links."""
        proposal_manager = self.proposal_managers[problem_id]
        proposal_manager.update_proposal(
            proposal_id=proposal_id,
            name=name,
            description=description,
            status=status,
            extras=extras if extras else None,
        )
        if related_scenario_ids is not None:
            self.problem_manager.set_related_scenario_ids(
                problem_id,
                proposal_id,
                related_scenario_ids,
            )

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Delete a proposal and persist the resulting aggregate."""
        self.proposal_managers[problem_id].delete_proposal(proposal_id)
        self.problem_manager.unlink_proposal(problem_id, proposal_id)

    def proposal_extras_from_dict(self, proposal_dict: dict) -> dict:
        """Extract proposal extras from a dictionary."""
        return self.extras_config.proposal_extras_from_dict(proposal_dict)
