# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.proposal.manager import ProposalManager
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.utils.exception import (
    ProposalAlreadyExists,
    ProposalDoesNotExist,
)

from overtourism.dt_manager.proposal import manager as proposal_manager_module
from overtourism.dt_manager.proposal import proposal as proposal_module

CREATED_TIMESTAMP = "2026-05-15T08:00:00Z"
UPDATED_TIMESTAMP = "2026-05-15T09:00:00Z"


def test_add_update_save_load_and_delete_proposal(
    local_store,
    problem_payload,
    monkeypatch,
) -> None:
    problem_id = problem_payload["problem_id"]
    manager = ProposalManager(problem_id, local_store)

    monkeypatch.setattr(proposal_module, "get_timestamp", lambda: CREATED_TIMESTAMP)
    monkeypatch.setattr(
        proposal_manager_module, "get_timestamp", lambda: UPDATED_TIMESTAMP
    )

    proposal = manager.add_proposal(
        "proposal-alpha",
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
    assert manager.get_proposal("proposal-alpha") is proposal

    with pytest.raises(ProposalAlreadyExists):
        manager.add_proposal("proposal-alpha")

    manager.save_proposal("proposal-alpha")
    assert local_store.load_proposals(problem_id) == [proposal.to_dict()]

    updated = manager.update_proposal(
        "proposal-alpha",
        name="Proposal Alpha Updated",
        description="Updated proposal",
        status="published",
        extras={"priority": "high"},
    )

    assert updated.updated == UPDATED_TIMESTAMP
    assert updated.name == "Proposal Alpha Updated"
    assert updated.description == "Updated proposal"
    assert updated.status == "published"
    assert updated.extras == {"kind": "proposal", "priority": "high"}

    manager.save_proposal("proposal-alpha")
    assert local_store.load_proposals(problem_id) == [updated.to_dict()]

    manager.delete_proposal("proposal-alpha")
    assert local_store.load_proposals(problem_id) == []

    with pytest.raises(ProposalDoesNotExist):
        manager.get_proposal("proposal-alpha")


def test_load_proposals_and_register_loaded_objects(
    local_store,
    problem_payload,
    proposal_payload,
    other_proposal_payload,
) -> None:
    problem_id = problem_payload["problem_id"]
    local_store.save_proposal(
        problem_id, proposal_payload["proposal_id"], proposal_payload
    )
    local_store.save_proposal(
        problem_id,
        other_proposal_payload["proposal_id"],
        other_proposal_payload,
    )

    manager = ProposalManager(problem_id, local_store)
    loaded = manager.load_proposals()

    assert [item.proposal_id for item in loaded] == [
        proposal_payload["proposal_id"],
        other_proposal_payload["proposal_id"],
    ]
    assert loaded[0].to_dict() == proposal_payload
    assert loaded[1].to_dict() == other_proposal_payload

    transient = Proposal(
        proposal_id="proposal-gamma",
        problem_id="",
        name="Proposal Gamma",
        description="Transient proposal",
        status="draft",
        created="2026-05-15T10:00:00Z",
        updated="2026-05-15T10:00:00Z",
        extras={"kind": "proposal"},
    )
    manager.load_proposal(transient)

    assert manager.get_proposal("proposal-gamma").problem_id == problem_id
    assert manager.list_proposals()["proposal-gamma"].name == "Proposal Gamma"
