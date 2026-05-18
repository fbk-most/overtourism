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
        self.proposals: dict[str, Proposal] = {}

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def add_proposal(
        self,
        proposal_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Create and register a new proposal.

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
        if proposal_id in self.proposals:
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
        self.proposals[proposal_id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal:
        """Return a registered proposal.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to retrieve.

        Returns
        -------
        Proposal
            Registered proposal instance.
        """
        if proposal_id not in self.proposals:
            raise ProposalDoesNotExist(f"Proposal with ID {proposal_id} does not exist")
        return self.proposals[proposal_id]

    def update_proposal(
        self,
        proposal_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Update a proposal in memory.

        Name, description, status, and extras are updated in place on the
        stored metadata. Any change that touches metadata refreshes the
        timestamp through :func:`update_metadata`.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to update.
        name : str | None, optional
            New proposal name.
        description : str | None, optional
            New proposal description.
        status : str | None, optional
            New proposal status.
        extras : dict | None, optional
            Extra metadata to merge into the proposal.

        Returns
        -------
        Proposal
            Updated proposal instance.
        """
        proposal = self.get_proposal(proposal_id)
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
            proposal.updated = get_timestamp()
        return proposal

    def delete_proposal(self, proposal_id: str) -> None:
        """Delete a proposal from memory and storage.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to delete.
        """
        if proposal_id not in self.proposals:
            raise ProposalDoesNotExist(f"Proposal with ID {proposal_id} does not exist")
        self.proposals.pop(proposal_id)
        self.store.delete_proposal(self.problem_id, proposal_id)

    # ───────────────────────────────────────────────────────────
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_proposal(self, proposal_id: str) -> Proposal:
        """Persist a proposal to storage.

        The saved payload contains the proposal metadata and its parent
        problem identifier. Proposal-scenario links are managed elsewhere by
        the relationship manager.

        Parameters
        ----------
        proposal_id : str
            Identifier of the proposal to save.

        Returns
        -------
        Proposal
            Proposal payload written to storage.
        """
        proposal = self.get_proposal(proposal_id)
        proposal.problem_id = self.problem_id
        self.store.save_proposal(self.problem_id, proposal_id, proposal.to_dict())
        return proposal

    def load_proposal(self, proposal_data: Proposal) -> None:
        """Load a proposal object into memory.

        Parameters
        ----------
        proposal_data : Proposal
            Proposal loaded from storage.
        """
        if proposal_data.proposal_id in self.proposals:
            return
        proposal = Proposal(
            proposal_id=proposal_data.proposal_id,
            problem_id=proposal_data.problem_id or self.problem_id,
            name=proposal_data.name,
            description=proposal_data.description,
            status=proposal_data.status,
            created=proposal_data.created,
            updated=proposal_data.updated,
            extras=proposal_data.extras,
        )
        self.proposals[proposal_data.proposal_id] = proposal

    def load_proposals(self) -> list[Proposal]:
        """Load all proposals for the problem from storage.

        Returns
        -------
        list[Proposal]
            Proposals returned by the store.
        """
        return [
            self._build_proposal(proposal_data)
            for proposal_data in self.store.load_proposals(self.problem_id)
        ]

    # ───────────────────────────────────────────────────────────
    # Accessors
    # ───────────────────────────────────────────────────────────

    def list_proposals(self) -> dict[str, Proposal]:
        """Return the in-memory proposal mapping.

        Returns
        -------
        dict[str, Proposal]
            Registered proposals keyed by proposal ID.
        """
        return self.proposals

    def _build_proposal(self, proposal_data: dict) -> Proposal:
        return Proposal.from_dict(proposal_data)
