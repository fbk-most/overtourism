# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.stores.classes.base import Store


class RelationshipManager:
    """Manage proposal-scenario relationships."""

    def __init__(
        self,
        store: Store,
    ) -> None:
        self.store = store

    def get_relationships(self) -> list[dict[str, str]]:
        """Return the current relationship links."""
        return self._normalize_relationships(self.store.load_relationships())

    def get_related_scenario_ids(
        self,
        proposal_id: str,
    ) -> list[str]:
        """Return the scenario IDs linked to a proposal."""
        return [
            relationship["scenario_id"]
            for relationship in self.get_relationships()
            if relationship["proposal_id"] == proposal_id
        ]

    def set_related_scenario_ids(
        self,
        proposal_id: str,
        scenario_ids: list[str],
    ) -> None:
        """Replace the scenarios linked to a proposal."""
        retained = [
            relationship
            for relationship in self.get_relationships()
            if relationship["proposal_id"] != proposal_id
        ]
        retained.extend(
            {
                "proposal_id": proposal_id,
                "scenario_id": scenario_id,
            }
            for scenario_id in scenario_ids
        )
        self._save_relationships(retained)

    def link_scenario_proposal(
        self,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Link a scenario to a proposal."""
        relationships = self.get_relationships()
        relationships.append({"proposal_id": proposal_id, "scenario_id": scenario_id})
        self._save_relationships(relationships)

    def unlink_scenario_proposal(
        self,
        proposal_id: str,
        scenario_id: str,
    ) -> None:
        """Remove a single scenario-proposal link."""
        relationships = [
            relationship
            for relationship in self.get_relationships()
            if relationship["proposal_id"] != proposal_id
            or relationship["scenario_id"] != scenario_id
        ]
        self._save_relationships(relationships)

    def _save_relationships(
        self,
        relationships: list[dict[str, str]],
    ) -> None:
        self.store.save_relationships(self._normalize_relationships(relationships))

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
