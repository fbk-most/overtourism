# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.enums import ProblemDocumentKey
from overtourism.dt_manager.utils.utils import get_timestamp


class ProblemManager:
    """Manage problem entities and persist them with their child documents.

    Problem metadata remains the source of truth for the problem itself, while
    proposal-scenario links are serialized under the top-level
    ``relationship`` section.

    Parameters
    ----------
    store : Store
        Persistence backend used to load and save problem data.
    """

    def __init__(
        self,
        store: Store,
    ) -> None:
        self.store = store
        self.problems: dict[str, Problem] = {}
        self._relationships: dict[str, list[dict[str, str]]] = {}

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_problem(
        self,
        problem_id: str,
        **kwargs,
    ) -> None:
        """Create and register a new problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to create.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`Problem.create_default`.
        """
        problem = Problem.create_default(problem_id, **kwargs)
        self.problems[problem_id] = problem

    def read_problem(self, problem_id: str) -> Problem:
        """Return a registered problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to return.

        Returns
        -------
        Problem
            Registered problem instance.
        """
        return self.problems[problem_id]

    def update_problem(self, problem_id: str, **kwargs) -> None:
        """Update a registered problem with new metadata."""

        updated = False
        problem = self.problems[problem_id]
        name = kwargs.pop("name", None)
        if name is not None:
            problem.name = name
            updated = True
        description = kwargs.pop("description", None)
        if description is not None:
            problem.description = description
            updated = True
        extras = kwargs.pop("extras", None)
        if extras is not None:
            for key, value in extras.items():
                problem.extras[key] = value
            updated = True
        if updated:
            problem.updated = get_timestamp()
            self.problems[problem_id] = problem

    def delete_problem(self, problem_id: str) -> None:
        """Remove a problem from memory and storage.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        self.problems.pop(problem_id, None)
        self._relationships.pop(problem_id, None)
        self.store.delete_problem(problem_id)

    # ───────────────────────────────────────────────────────────
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_problem(self, problem_id: str) -> None:
        """Persist a problem and its child documents.

        The problem payload is written together with the current scenario and
        proposal sections. Any stored top-level ``relationship`` section is
        preserved alongside the rest of the document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to save.
        """
        problem = self.read_problem(problem_id)
        scenarios = self._load_optional_items(
            lambda: (
                scenario.to_dict() for scenario in self.store.load_scenarios(problem_id)
            )
        )
        proposals = self._load_optional_items(
            lambda: (
                proposal.to_dict() for proposal in self.store.load_proposals(problem_id)
            )
        )
        evaluations = self._load_optional_items(
            lambda: (
                evaluation.to_dict()
                for evaluation in self.store.load_evaluations(problem_id)
            )
        )

        payload = {
            ProblemDocumentKey.PROBLEM: problem.to_dict(),
            ProblemDocumentKey.SCENARIOS: scenarios,
            ProblemDocumentKey.PROPOSALS: proposals,
            ProblemDocumentKey.EVALUATIONS: evaluations,
            ProblemDocumentKey.RELATIONSHIP: self.get_relationships(problem_id),
        }
        self.store.save_problem_document(problem.problem_id, payload)

    def load_problem(self, problem_id: str) -> None:
        """Load a problem from storage into memory.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to load.
        """
        problem = self.store.load_problem(problem_id)
        self.problems[problem.problem_id] = problem
        self.load_relationships(problem.problem_id)

    def load_problems(self, problem_ids: list[str] | None = None) -> None:
        """Load multiple problems from storage.

        Parameters
        ----------
        problem_ids : list[str] | None, optional
            Identifiers of the problems to load. When omitted, all
            problems reported by the store are loaded.
        """
        if problem_ids is None:
            problem_ids = self.store.list_problems()

        for problem_id in problem_ids:
            self.load_problem(problem_id)

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    def load_relationships(self, problem_id: str) -> None:
        """Load proposal-scenario links for a problem."""
        try:
            document = self.store.load_problem_document(problem_id)
        except FileNotFoundError:
            self._relationships[problem_id] = []
            return

        relationships: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in document.get(ProblemDocumentKey.RELATIONSHIP, []):
            proposal_id = item.get("proposal_id")
            scenario_id = item.get("scenario_id")
            if not proposal_id or not scenario_id:
                continue
            pair = (proposal_id, scenario_id)
            if pair in seen:
                continue
            seen.add(pair)
            relationships.append(
                {"proposal_id": proposal_id, "scenario_id": scenario_id}
            )

        self._relationships[problem_id] = relationships

    def get_relationships(self, problem_id: str) -> list[dict[str, str]]:
        """Return the current relationship links for a problem."""
        self._load_relationships_if_needed(problem_id)
        return list(self._relationships.get(problem_id, []))

    def get_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
    ) -> list[str]:
        """Return the scenario IDs linked to a proposal."""
        self._load_relationships_if_needed(problem_id)
        return [
            relationship["scenario_id"]
            for relationship in self._relationships.get(problem_id, [])
            if relationship["proposal_id"] == proposal_id
        ]

    def set_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_ids: list[str],
    ) -> None:
        """Replace the scenarios linked to a proposal."""
        self._load_relationships_if_needed(problem_id)
        retained = [
            relationship
            for relationship in self._relationships.get(problem_id, [])
            if relationship["proposal_id"] != proposal_id
        ]
        retained.extend(
            {
                "proposal_id": proposal_id,
                "scenario_id": scenario_id,
            }
            for scenario_id in dict.fromkeys(scenario_ids)
        )
        self._relationships[problem_id] = retained

    def link_scenario_to_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal."""
        self._load_relationships_if_needed(problem_id)
        relationship = {"proposal_id": proposal_id, "scenario_id": scenario_id}
        relationships = self._relationships.setdefault(problem_id, [])
        if relationship not in relationships:
            relationships.append(relationship)

    def unlink_scenario(self, problem_id: str, scenario_id: str) -> None:
        """Remove all links for a scenario."""
        self._load_relationships_if_needed(problem_id)
        self._relationships[problem_id] = [
            relationship
            for relationship in self._relationships.get(problem_id, [])
            if relationship["scenario_id"] != scenario_id
        ]

    def unlink_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Remove all links for a proposal."""
        self._load_relationships_if_needed(problem_id)
        self._relationships[problem_id] = [
            relationship
            for relationship in self._relationships.get(problem_id, [])
            if relationship["proposal_id"] != proposal_id
        ]

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _load_relationships_if_needed(self, problem_id: str) -> None:
        if problem_id not in self._relationships:
            self.load_relationships(problem_id)
