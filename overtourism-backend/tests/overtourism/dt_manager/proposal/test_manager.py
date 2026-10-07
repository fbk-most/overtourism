# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.proposal import manager as proposal_manager_module
from overtourism.dt_manager.proposal import proposal as proposal_module
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    ProposalAlreadyExists,
)

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
UPDATED_TIMESTAMP = "2026-05-15T09:00:00Z"


def test_add_update_save_load_and_delete_proposal(
    sql_store,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = ProposalManager(sql_store)
    sql_store.save_problem(problem_payload)

    monkeypatch.setattr(proposal_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        proposal_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    proposal = manager.create_proposal(
        "proposal-alpha",
        problem_id,
        name="Proposal Alpha",
        description="Primary proposal",
        status="draft",
        extras={"kind": "proposal"},
    )

    assert proposal.problem_id == problem_id
    assert proposal.created == CREATED_TIMESTAMP
    assert proposal.updated == CREATED_TIMESTAMP
    assert proposal.name == "Proposal Alpha"
    assert proposal.description == "Primary proposal"
    assert proposal.status == "draft"
    assert proposal.extras == {"kind": "proposal"}
    assert sql_store.load_proposals(problem_id) == [proposal.to_dict()]
    assert manager.read_proposal("proposal-alpha").to_dict() == proposal.to_dict()

    with pytest.raises(ProposalAlreadyExists):
        manager.create_proposal("proposal-alpha", problem_id)

    updated = manager.update_proposal(
        "proposal-alpha",
        name="Proposal Alpha Updated",
        description="Updated proposal",
        status="accepted",
        extras={"priority": "high"},
    )

    assert updated.updated == UPDATED_TIMESTAMP
    assert updated.name == "Proposal Alpha Updated"
    assert updated.description == "Updated proposal"
    assert updated.status == "accepted"
    assert updated.extras == {"kind": "proposal", "priority": "high"}

    assert sql_store.load_proposals(problem_id) == [updated.to_dict()]

    manager.delete_proposal("proposal-alpha")
    assert sql_store.load_proposals(problem_id) == []

    with pytest.raises(EntityDoesNotExist):
        manager.read_proposal("proposal-alpha")


def test_list_proposals_reads_persisted_objects(
    sql_store,
    problem_payload,
    scenario_payload,
    proposal_payload,
    other_proposal_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    sql_store.save_problem(problem_payload)
    sql_store.save_scenario(scenario_payload)
    sql_store.save_proposal(proposal_payload)
    sql_store.save_proposal(other_proposal_payload)
    sql_store.save_relationships(
        [
            {
                "proposal_id": proposal_payload["proposal_id"],
                "scenario_id": scenario_payload["scenario_id"],
            }
        ]
    )

    manager = ProposalManager(sql_store)
    loaded = manager.list_proposals(problem_id=problem_id)

    assert [item.proposal_id for item in loaded] == [
        proposal_payload["proposal_id"],
        other_proposal_payload["proposal_id"],
    ]
    assert loaded[0].to_dict() == proposal_payload
    assert loaded[1].to_dict() == other_proposal_payload
    assert [
        item.proposal_id
        for item in manager.list_proposals(scenario_id=scenario_payload["scenario_id"])
    ] == [
        proposal_payload["proposal_id"],
    ]

    reloaded_manager = ProposalManager(sql_store)
    assert (
        reloaded_manager.read_proposal("proposal-alpha").to_dict() == proposal_payload
    )
