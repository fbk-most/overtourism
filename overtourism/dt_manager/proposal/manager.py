# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.proposal.proposal import Proposal, ProposalStatus
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    ProposalAlreadyExists,
    ProposalDoesNotExist,
)
from overtourism.dt_manager.utils.utils import get_timestamp


class ProposalManager:
    """Manage proposal entities for a single problem.

    Parameters
    ----------
    problem_id : str
        Identifier of the parent problem.
    store : Store
        Persistence backend used for proposal data.
    """

    def __init__(self, problem_id: str, store: Store) -> None:
        """Create a proposal manager bound to a problem."""
        self.problem_id = problem_id
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_proposal(
        self,
        proposal_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Create and persist a new proposal.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to create.
        name : str | None, optional
            Optional proposal name.
        description : str | None, optional
            Optional proposal description.
        status : str | None, optional
            Optional proposal status.
        extras : dict | None, optional
            Optional metadata extras.
        Returns
        -------
        Proposal
            Proposal created for the problem.
        """
        try:
            self.store.load_proposal(self.problem_id, proposal_id)
        except ProposalDoesNotExist:
            pass
        else:
            raise ProposalAlreadyExists(
                f"Proposal with ID {proposal_id} already exists"
            )

        proposal = Proposal.create_default(
            proposal_id,
            problem_id=self.problem_id,
            name=name,
            description=description,
            status=status,
            extras=extras,
        )
        self.store.save_proposal(self.problem_id, proposal_id, proposal.to_dict())
        return proposal

    def read_proposal(self, proposal_id: str) -> Proposal:
        """Return a persisted proposal.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to retrieve.

        Returns
        -------
        Proposal
            Persisted proposal instance.
        """
        return self._build_proposal(
            self.store.load_proposal(self.problem_id, proposal_id)
        )

    def list_proposals(self) -> list[Proposal]:
        """Return all persisted proposals for the problem."""
        return [
            self._build_proposal(proposal_data)
            for proposal_data in self.store.load_proposals(self.problem_id)
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
            self.store.save_proposal(self.problem_id, proposal_id, proposal.to_dict())
        return proposal

    def delete_proposal(self, proposal_id: str) -> None:
        """Delete a persisted proposal."""
        self.store.load_proposal(self.problem_id, proposal_id)
        self.store.delete_proposal(self.problem_id, proposal_id)

    def _build_proposal(self, proposal_data: dict) -> Proposal:
        return Proposal.from_dict(proposal_data)
