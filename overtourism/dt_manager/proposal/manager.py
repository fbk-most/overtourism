# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.proposal.proposal import Proposal, ProposalStatus
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    ProposalAlreadyExists,
)
from overtourism.dt_manager.utils.utils import get_timestamp


class ProposalManager:
    """Manage proposal entities for a single problem."""

    def __init__(self, store: Store) -> None:
        """Create a proposal manager bound to a problem."""
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_proposal(
        self,
        proposal_id: str,
        problem_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Create and persist a new proposal."""
        try:
            self.store.load_proposal(proposal_id)
        except EntityDoesNotExist:
            pass
        else:
            raise ProposalAlreadyExists(
                f"Proposal with ID {proposal_id} already exists"
            )

        proposal = Proposal.create_default(
            proposal_id,
            problem_id=problem_id,
            name=name,
            description=description,
            status=status,
            extras=extras,
        )
        self.store.save_proposal(proposal.to_dict())
        return proposal

    def read_proposal(
        self,
        proposal_id: str,
        tenant: str | None = None,
    ) -> Proposal:
        """Return a persisted proposal."""
        return Proposal.from_dict(self.store.load_proposal(proposal_id, tenant=tenant))

    def list_proposals(
        self,
        problem_id: str | None = None,
        scenario_id: str | None = None,
        tenant: str | None = None,
    ) -> list[Proposal]:
        """Return all persisted proposals for the problem."""
        return [
            Proposal.from_dict(proposal_data)
            for proposal_data in self.store.load_proposals(
                problem_id,
                scenario_id,
                tenant=tenant,
            )
        ]

    def update_proposal(
        self,
        proposal_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Update a persisted proposal."""
        proposal = self.read_proposal(proposal_id)
        updated = False

        if name is not None:
            proposal.name = name
            updated = True
        if description is not None:
            proposal.description = description
            updated = True
        if status is not None:
            proposal.status = (
                status if isinstance(status, ProposalStatus) else ProposalStatus(status)
            )
            updated = True
        if extras is not None:
            proposal.extras.update(extras)
            updated = True

        if updated:
            proposal.version += 1
            proposal.updated = get_timestamp()
            self.store.save_proposal(proposal.to_dict())
        return proposal

    def delete_proposal(self, proposal_id: str) -> None:
        """Delete a persisted proposal."""
        self.store.delete_proposal(proposal_id)
