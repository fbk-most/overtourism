# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from uuid import uuid4

from civic_digital_twins.dt_model.model import Model

from overtourism.dt_manager.classes.metadata import ExtrasConfig
from overtourism.dt_manager.classes.model import ModelEvaluator
from overtourism.dt_manager.evaluation.manager import EvaluationManager
from overtourism.dt_manager.executor.executor import Executor
from overtourism.dt_manager.manager.relationships import RelationshipManager
from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.scenario.manager import ScenarioManager
from overtourism.dt_manager.scenario.values import values_as_scipy
from overtourism.dt_manager.stores.builder import create_store
from overtourism.dt_manager.stores.config import StoreConfig


class Manager:
    """Facade exposing problem, scenario, proposal, and relationship managers.

    Proposal-scenario links are managed separately from proposal and scenario
    entities so they can be persisted in the dedicated relationship store and
    serialized under the top-level ``relationship`` section in local JSON.
    ``extras_config`` is stored on the facade so the API layer can extract
    problem, proposal, and scenario extras consistently.

    Parameters
    ----------
    model : Model
        Base model used to build scenario managers.
    model_evaluator : ModelEvaluator
        Evaluator used to compute scenario outputs and index diffs.
    store_config : StoreConfig
        Storage configuration used to build the persistence backend.
    extras_config : ExtrasConfig | None, optional
        Optional metadata extras configuration.
    """

    def __init__(
        self,
        model: Model,
        model_evaluator: ModelEvaluator,
        store_config: StoreConfig,
        extras_config: ExtrasConfig | None = None,
    ) -> None:
        """Create the high-level manager facade and relationship manager."""
        self.model = model
        self.model_evaluator = model_evaluator
        self.extras_config = extras_config

        self.store = create_store(store_config.store_type, **store_config.config)
        self.executor = Executor(self.model, self.model_evaluator)

        self.problem_manager = ProblemManager(self.store)
        self.scenario_managers: dict[str, ScenarioManager] = {}
        self.evaluation_managers: dict[str, EvaluationManager] = {}
        self.proposal_managers: dict[str, ProposalManager] = {}
        self.relationship_manager = RelationshipManager(self.store)

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def get_problem(self, problem_id: str):
        """Return a loaded problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to retrieve.

        Returns
        -------
        Problem
            Loaded problem instance.
        """
        return self.problem_manager.get_problem(problem_id)

    def list_problems(self) -> list[str]:
        """Return the loaded problem identifiers.

        Returns
        -------
        list[str]
            Registered problem identifiers.
        """
        return list(self.problem_manager.problems.keys())

    def add_problem(self, problem_id: str, **kwargs) -> None:
        """Create a problem and initialize its child managers.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to create.
        **kwargs
            Additional keyword arguments forwarded to the problem manager.
        """
        self.problem_manager.add_problem(problem_id, **kwargs)
        self.evaluation_managers[problem_id] = EvaluationManager(
            self.executor,
            self.store,
            problem_id,
        )
        self.scenario_managers[problem_id] = ScenarioManager(
            problem_id,
            self.model,
            self.model_evaluator,
            self.store,
        )
        self.proposal_managers[problem_id] = ProposalManager(problem_id, self.store)

    def load_problem(self, problem_id: str) -> None:
        """Load a problem and hydrate its scenarios and proposals.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to load.
        """
        self.problem_manager.load_problem(problem_id)
        self.evaluation_managers[problem_id] = EvaluationManager(
            self.executor,
            self.store,
            problem_id,
        )
        self.scenario_managers[problem_id] = ScenarioManager(
            problem_id,
            self.model,
            self.model_evaluator,
            self.store,
        )
        self.proposal_managers[problem_id] = ProposalManager(problem_id, self.store)

        for scenario_data in self.scenario_managers[problem_id].load_scenarios():
            self.scenario_managers[problem_id].load_scenario(
                scenario_data,
                values_as_scipy(scenario_data),
            )

        for proposal_data in self.proposal_managers[problem_id].load_proposals():
            self.proposal_managers[problem_id].load_proposal(proposal_data)

        self.evaluation_managers[problem_id].load_evaluations()

    def load_problems(self, problem_ids: list[str] | None = None) -> None:
        """Load multiple problems from storage.

        Parameters
        ----------
        problem_ids : list[str] | None, optional
            Problem identifiers to load. When omitted, every problem in the
            store is loaded.
        """
        if problem_ids is None:
            problem_ids = self.store.list_problems()

        for problem_id in problem_ids:
            self.load_problem(problem_id)

    def save_problem(self, problem_id: str) -> None:
        """Persist a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to save.
        """
        self.problem_manager.save_problem(problem_id)

    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem and clear its child managers and cached relationships.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        self.problem_manager.delete_problem(problem_id)
        self.evaluation_managers.pop(problem_id, None)
        self.scenario_managers.pop(problem_id, None)
        self.proposal_managers.pop(problem_id, None)
        self.relationship_manager.delete_relationships(problem_id)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def add_scenario(self, problem_id: str, scenario_id: str, **kwargs) -> None:
        """Create a scenario under a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        scenario_id : str
            Identifier of the scenario to create.
        **kwargs
            Additional keyword arguments forwarded to the scenario manager.
        """
        self.get_scenario_manager(problem_id).add_scenario(scenario_id, **kwargs)

    def get_scenario_manager(self, problem_id: str) -> ScenarioManager:
        """Return the scenario manager for a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem.

        Returns
        -------
        ScenarioManager
            Problem-specific scenario manager.
        """
        return self.scenario_managers[problem_id]

    def get_evaluation_manager(self, problem_id: str) -> EvaluationManager:
        """Return the evaluation manager for a problem."""
        return self.evaluation_managers[problem_id]

    def get_session_scenario(self, problem_id: str, session_id: str):
        """Return a transient scenario for a session."""
        return self.get_scenario_manager(problem_id).get_session_scenario(session_id)

    def get_session_evaluation(self, problem_id: str, session_id: str):
        """Return the transient evaluation attached to a session."""
        return self.get_evaluation_manager(problem_id).get_session_evaluation(
            session_id
        )

    def close_session(self, problem_id: str, session_id: str) -> None:
        """Close a session and discard both scenario and evaluation state."""
        self.get_scenario_manager(problem_id).close_session(session_id)
        self.get_evaluation_manager(problem_id).close_session(session_id)

    def get_scenario_data(self, problem_id: str, scenario_id: str):
        """Return the latest stored evaluation result for a scenario.

        If no evaluation exists yet, create one on demand and return its result.
        """
        try:
            result = (
                self.get_evaluation_manager(problem_id)
                .get_latest_evaluation(scenario_id)
                .result
            )
        except Exception:
            result = self.evaluate_scenario(problem_id, scenario_id).result
        return result.to_dict() if hasattr(result, "to_dict") else result

    def evaluate_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ):
        """Evaluate a stored scenario and persist the evaluation state."""
        scenario_manager = self.get_scenario_manager(problem_id)
        evaluation_manager = self.get_evaluation_manager(problem_id)
        try:
            scenario = scenario_manager.get_scenario(scenario_id)
        except Exception:
            scenario = scenario_manager.add_scenario(scenario_id)

        scenario.is_evaluating = True
        evaluation_id = f"{scenario.scenario_id}_{uuid4().hex}"
        evaluation_manager.create_evaluation(
            evaluation_id,
            scenario.scenario_id,
        )
        try:
            return evaluation_manager.run_evaluation(
                evaluation_id,
                scenario,
                ensemble_size=ensemble_size,
                **kwargs,
            )
        finally:
            scenario.is_evaluating = False

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
        scenario_manager = self.get_scenario_manager(problem_id)
        evaluation_manager = self.get_evaluation_manager(problem_id)
        session_scenario = scenario_manager.create_session_scenario(scenario_id, values)
        session_scenario.is_evaluating = True
        evaluation_id = f"{session_id}_{uuid4().hex}"
        evaluation_manager.create_evaluation(
            evaluation_id,
            session_scenario.scenario_id,
        )
        try:
            evaluation = evaluation_manager.run_evaluation(
                evaluation_id,
                session_scenario,
                ensemble_size=ensemble_size,
                **kwargs,
            )
            evaluation_manager.set_session_evaluation(session_id, evaluation)
            scenario_manager.register_session_scenario(session_id, session_scenario)
            return session_scenario
        finally:
            session_scenario.is_evaluating = False

    def save_scenario(
        self,
        problem_id: str,
        scenario_id: str,
    ) -> None:
        """Persist a scenario inside its parent problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        scenario_id : str
            Identifier of the scenario to save.
        """
        self.get_scenario_manager(problem_id).save_scenario(
            scenario_id,
        )

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        """Delete a scenario and remove any related proposal links."""
        self.get_scenario_manager(problem_id).delete_scenario(scenario_id)
        self.relationship_manager.unlink_scenario(problem_id, scenario_id)

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def add_proposal(self, problem_id: str, proposal_id: str, **kwargs) -> None:
        """Create a proposal under a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        proposal_id : str
            Identifier of the proposal to create.
        **kwargs
            Additional keyword arguments forwarded to the proposal manager.
        """
        self.get_proposal_manager(problem_id).add_proposal(proposal_id, **kwargs)

    def get_proposal_manager(self, problem_id: str) -> ProposalManager:
        """Return the proposal manager for a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem.

        Returns
        -------
        ProposalManager
            Problem-specific proposal manager.
        """
        return self.proposal_managers[problem_id]

    def link_scenario_to_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal through the relationship manager."""
        self.relationship_manager.link_scenario_to_proposal(
            problem_id,
            proposal_id,
            scenario_id,
        )

    def set_related_scenario_ids_for_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_ids: list[str],
    ) -> None:
        """Replace the scenarios linked to a proposal through the relationship manager."""
        self.relationship_manager.set_related_scenario_ids(
            problem_id,
            proposal_id,
            scenario_ids,
        )

    def get_related_scenario_ids_for_proposal(
        self,
        problem_id: str,
        proposal_id: str,
    ) -> list[str]:
        """Return the scenario identifiers linked to a proposal."""
        return self.relationship_manager.get_related_scenario_ids(
            problem_id,
            proposal_id,
        )

    def unlink_scenario_from_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Unlink a scenario from a proposal through the relationship manager."""
        self.relationship_manager.unlink_scenario_from_proposal(
            problem_id,
            proposal_id,
            scenario_id,
        )

    def save_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Persist a proposal without touching relationship links."""
        self.get_proposal_manager(problem_id).save_proposal(proposal_id)

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Delete a proposal and remove any relationship links."""
        self.get_proposal_manager(problem_id).delete_proposal(proposal_id)
        self.relationship_manager.unlink_proposal(problem_id, proposal_id)
