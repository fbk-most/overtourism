# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.proposal.proposal import Proposal

from overtourism.dt_manager.proposal import proposal as proposal_module

FIXED_TIMESTAMP = "2026-05-15T12:34:56Z"


def test_create_default_uses_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(proposal_module, "get_timestamp", lambda: FIXED_TIMESTAMP)

    proposal = Proposal.create_default("proposal-alpha")

    assert proposal.to_dict() == {
        "proposal_id": "proposal-alpha",
        "problem_id": "",
        "name": "proposal-alpha",
        "description": "",
        "status": "draft",
        "created": FIXED_TIMESTAMP,
        "updated": FIXED_TIMESTAMP,
        "extras": {},
    }


def test_from_dict_round_trip() -> None:
    payload = {
        "proposal_id": "proposal-alpha",
        "problem_id": "problem-alpha",
        "name": "Proposal Alpha",
        "description": "Primary proposal",
        "status": "published",
        "created": "2026-05-15T10:00:00Z",
        "updated": "2026-05-15T11:00:00Z",
        "extras": {"kind": "proposal"},
    }

    proposal = Proposal.from_dict(payload)

    assert proposal.to_dict() == payload
