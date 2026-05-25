# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.utils import get_timestamp


class ProblemManager:
    """Manage problem entities directly against the store.

    Problem metadata is persisted immediately, while proposal-scenario links
    live in the top-level ``relationship`` section of the problem document.

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

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_problem(
        self,
        problem_id: str,
        **kwargs,
    ) -> None:
        """Create and persist a new problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to create.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`Problem.create_default`.
        """
        problem = Problem.create_default(problem_id, **kwargs)
        self.store.save_problem(
            problem_id,
            problem.to_dict(),
        )

    def read_problem(self, problem_id: str) -> Problem:
        """Return a problem loaded from the store.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to return.

        Returns
        -------
        Problem
            Persisted problem instance.
        """
        return Problem.from_dict(self.store.load_problem(problem_id))

    def list_problems(self) -> list[Problem]:
        """Return all persisted problems."""
        return [
            Problem.from_dict(problem_data)
            for problem_data in self.store.load_problems()
        ]

    def update_problem(self, problem_id: str, **kwargs) -> None:
        """Update a persisted problem with new metadata."""

        updated = False
        problem = self.read_problem(problem_id)
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
            problem.version += 1
            problem.updated = get_timestamp()
            self.store.save_problem(problem_id, problem.to_dict())

    def delete_problem(self, problem_id: str) -> None:
        """Remove a problem from storage.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        self.store.delete_problem(problem_id)

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    def get_relationships(self, problem_id: str) -> list[dict[str, str]]:
        """Return the current relationship links for a problem."""
        return self._normalize_relationships(self.store.load_relationships(problem_id))

    def get_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
    ) -> list[str]:
        """Return the scenario IDs linked to a proposal."""
        return [
            relationship["scenario_id"]
            for relationship in self.get_relationships(problem_id)
            if relationship["proposal_id"] == proposal_id
        ]

    def set_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_ids: list[str],
    ) -> None:
        """Replace the scenarios linked to a proposal."""
        retained = [
            relationship
            for relationship in self.get_relationships(problem_id)
            if relationship["proposal_id"] != proposal_id
        ]
        retained.extend(
            {
                "proposal_id": proposal_id,
                "scenario_id": scenario_id,
            }
            for scenario_id in scenario_ids
        )
        self._save_relationships(problem_id, retained)

    def link_scenario_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal."""
        relationships = self.get_relationships(problem_id)
        relationships.append({"proposal_id": proposal_id, "scenario_id": scenario_id})
        self._save_relationships(problem_id, relationships)

    def unlink_scenario_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Remove a single scenario-proposal link."""
        relationships = [
            relationship
            for relationship in self.get_relationships(problem_id)
            if relationship["proposal_id"] != proposal_id
            or relationship["scenario_id"] != scenario_id
        ]
        self._save_relationships(problem_id, relationships)

    def _save_relationships(
        self,
        problem_id: str,
        relationships: list[dict[str, str]],
    ) -> None:
        self.store.save_relationships(
            problem_id,
            self._normalize_relationships(relationships),
        )

    def _normalize_relationships(
        self,
        relationships: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in relationships:
            proposal_id = item.get("proposal_id")
            scenario_id = item.get("scenario_id")
            if not proposal_id or not scenario_id:
                continue
            pair = (proposal_id, scenario_id)
            if pair in seen:
                continue
            seen.add(pair)
            normalized.append({"proposal_id": proposal_id, "scenario_id": scenario_id})
        return normalized
