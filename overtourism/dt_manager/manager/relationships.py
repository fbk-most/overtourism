# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.enums import ProblemDocumentKey


class RelationshipManager:
    """Coordinate proposal-scenario relationship persistence.

    The manager owns the canonical many-to-many link set for each problem and
    stores it under the top-level ``relationship`` section in local JSON files.
    """

    def __init__(self, store: Store) -> None:
        self.store = store
        self._relationships: dict[str, list[tuple[str, str]]] = {}

    # ───────────────────────────────────────────────────────────
    # Persistence
    # ───────────────────────────────────────────────────────────

    def load_relationships(self, problem_id: str) -> None:
        """Load relationship links for a problem from storage.

        The stored document is read from the top-level ``relationship`` section.
        """
        try:
            document = self.store.load_problem_document(problem_id)
        except FileNotFoundError:
            self._relationships[problem_id] = []
            return

        relationships: list[tuple[str, str]] = []
        raw_relationships = document.get(ProblemDocumentKey.RELATIONSHIP, [])
        for item in raw_relationships:
            proposal_id = item.get("proposal_id")
            scenario_id = item.get("scenario_id")
            if proposal_id and scenario_id:
                pair = (proposal_id, scenario_id)
                if pair not in relationships:
                    relationships.append(pair)

        self._relationships[problem_id] = relationships

    def save_relationships(self, problem_id: str) -> None:
        """Persist relationship links for a problem.

        The relationship data is written back as a top-level ``relationship``
        array of ``{proposal_id, scenario_id}`` objects.
        """
        try:
            document = self.store.load_problem_document(problem_id)
        except FileNotFoundError:
            document = {}

        document[ProblemDocumentKey.RELATIONSHIP] = [
            {"proposal_id": proposal_id, "scenario_id": scenario_id}
            for proposal_id, scenario_id in self._relationships.get(problem_id, [])
        ]
        self.store.save_problem_document(problem_id, document)

    def get_relationships(self, problem_id: str) -> list[dict[str, str]]:
        """Return the current relationship links for a problem."""
        self._load_if_needed(problem_id)
        return [
            {"proposal_id": proposal_id, "scenario_id": scenario_id}
            for proposal_id, scenario_id in self._relationships.get(problem_id, [])
        ]

    def delete_relationships(self, problem_id: str) -> None:
        """Drop cached relationships for a problem."""
        self._relationships.pop(problem_id, None)

    # ───────────────────────────────────────────────────────────
    # Queries
    # ───────────────────────────────────────────────────────────

    def get_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
    ) -> list[str]:
        """Return the scenario IDs linked to a proposal."""
        self._load_if_needed(problem_id)
        return [
            scenario_id
            for current_proposal_id, scenario_id in self._relationships.get(
                problem_id,
                [],
            )
            if current_proposal_id == proposal_id
        ]

    # ───────────────────────────────────────────────────────────
    # Mutations
    # ───────────────────────────────────────────────────────────

    def set_related_scenario_ids(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_ids: list[str],
    ) -> None:
        """Replace the scenarios linked to a proposal."""
        self._load_if_needed(problem_id)
        retained = [
            pair
            for pair in self._relationships.get(problem_id, [])
            if pair[0] != proposal_id
        ]
        for scenario_id in dict.fromkeys(scenario_ids):
            retained.append((proposal_id, scenario_id))
        self._relationships[problem_id] = retained

    def link_scenario_to_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal and persist the relationship."""
        self._load_if_needed(problem_id)
        pair = (proposal_id, scenario_id)
        relationships = self._relationships.setdefault(problem_id, [])
        if pair not in relationships:
            relationships.append(pair)

    def unlink_scenario_from_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Unlink a scenario from a proposal and persist the relationship."""
        self._load_if_needed(problem_id)
        self._relationships[problem_id] = [
            pair
            for pair in self._relationships.get(problem_id, [])
            if pair != (proposal_id, scenario_id)
        ]

    def unlink_scenario(self, problem_id: str, scenario_id: str) -> None:
        """Remove all links for a scenario and persist the relationship."""
        self._load_if_needed(problem_id)
        self._relationships[problem_id] = [
            pair
            for pair in self._relationships.get(problem_id, [])
            if pair[1] != scenario_id
        ]

    def unlink_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Remove all links for a proposal and persist the relationship."""
        self._load_if_needed(problem_id)
        self._relationships[problem_id] = [
            pair
            for pair in self._relationships.get(problem_id, [])
            if pair[0] != proposal_id
        ]

    # ───────────────────────────────────────────────────────────
    # Internal helpers
    # ───────────────────────────────────────────────────────────

    def _load_if_needed(self, problem_id: str) -> None:
        if problem_id not in self._relationships:
            self.load_relationships(problem_id)
