# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.enums import ProblemDocumentKey


class ProblemManager:
    """Manage problem entities and persist them with their child documents.

    Problem metadata remains the source of truth for the problem itself, while
    proposal-scenario links are handled separately by RelationshipManager and
    serialized under the top-level ``relationship`` section.

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

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def add_problem(
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

    def get_problem(self, problem_id: str) -> Problem:
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
        problem = self.get_problem(problem_id)
        try:
            scenarios = [
                scenario.to_dict() for scenario in self.store.load_scenarios(problem_id)
            ]
        except FileNotFoundError:
            scenarios = []

        try:
            proposals = [
                proposal.to_dict() for proposal in self.store.load_proposals(problem_id)
            ]
        except FileNotFoundError:
            proposals = []

        try:
            evaluations = [
                evaluation.to_dict()
                for evaluation in self.store.load_evaluations(problem_id)
            ]
        except FileNotFoundError:
            evaluations = []

        try:
            document = self.store.load_problem_document(problem_id)
        except FileNotFoundError:
            document = {}

        payload = {
            ProblemDocumentKey.PROBLEM: problem.to_dict(),
            ProblemDocumentKey.SCENARIOS: scenarios,
            ProblemDocumentKey.PROPOSALS: proposals,
            ProblemDocumentKey.EVALUATIONS: evaluations,
        }
        if ProblemDocumentKey.RELATIONSHIP in document:
            payload[ProblemDocumentKey.RELATIONSHIP] = document[
                ProblemDocumentKey.RELATIONSHIP
            ]
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

    def delete_problem(self, problem_id: str) -> None:
        """Remove a problem from memory and storage.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        self.problems.pop(problem_id, None)
        self.store.delete_problem(problem_id)
