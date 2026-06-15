# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.relationship.manager import RelationshipManager


class FakeStore:
    def __init__(self, relationships: list[dict[str, str]] | None = None) -> None:
        self.relationships = list(relationships or [])
        self.saved_relationships: list[dict[str, str]] = []

    def load_relationships(self) -> list[dict[str, str]]:
        return list(self.relationships)

    def save_relationships(self, relationships: list[dict[str, str]]) -> None:
        self.relationships = list(relationships)
        self.saved_relationships = list(relationships)


def test_get_relationships_normalizes_invalid_and_duplicate_entries() -> None:
    store = FakeStore(
        [
            {"proposal_id": "proposal-alpha", "scenario_id": "scenario-alpha"},
            {"proposal_id": "proposal-alpha", "scenario_id": "scenario-alpha"},
            {"proposal_id": "proposal-alpha", "scenario_id": ""},
            {"proposal_id": "", "scenario_id": "scenario-beta"},
            {"proposal_id": "proposal-beta", "scenario_id": "scenario-beta"},
        ]
    )

    manager = RelationshipManager(store)

    assert manager.get_relationships() == [
        {"proposal_id": "proposal-alpha", "scenario_id": "scenario-alpha"},
        {"proposal_id": "proposal-beta", "scenario_id": "scenario-beta"},
    ]
    assert manager.get_related_scenario_ids("proposal-alpha") == ["scenario-alpha"]


def test_link_set_and_unlink_relationships() -> None:
    store = FakeStore(
        [{"proposal_id": "proposal-beta", "scenario_id": "scenario-beta"}]
    )
    manager = RelationshipManager(store)

    manager.link_scenario_proposal("proposal-alpha", "scenario-alpha")
    manager.link_scenario_proposal("proposal-alpha", "scenario-alpha")
    manager.set_related_scenario_ids(
        "proposal-alpha",
        ["scenario-alpha", "scenario-alpha", "scenario-gamma"],
    )

    assert manager.get_relationships() == [
        {"proposal_id": "proposal-beta", "scenario_id": "scenario-beta"},
        {"proposal_id": "proposal-alpha", "scenario_id": "scenario-alpha"},
        {"proposal_id": "proposal-alpha", "scenario_id": "scenario-gamma"},
    ]

    manager.unlink_scenario_proposal("proposal-alpha", "scenario-alpha")

    assert manager.get_relationships() == [
        {"proposal_id": "proposal-beta", "scenario_id": "scenario-beta"},
        {"proposal_id": "proposal-alpha", "scenario_id": "scenario-gamma"},
    ]
    assert manager.get_related_scenario_ids("proposal-alpha") == ["scenario-gamma"]
