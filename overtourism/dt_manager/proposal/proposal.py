# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from overtourism.dt_manager.classes.dictable import Dictable
from overtourism.dt_manager.utils.utils import get_timestamp


class ProposalStatus(str, Enum):
    """Lifecycle states for a proposal."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


def _coerce_status(status: ProposalStatus | str | None) -> ProposalStatus:
    if status is None:
        return ProposalStatus.DRAFT
    if isinstance(status, ProposalStatus):
        return status
    return ProposalStatus(status)


@dataclass
class Proposal(Dictable):
    """Domain entity for a proposal.

    Parameters
    ----------
    proposal_id : str
        Proposal identifier.
    problem_id : str
        Parent problem identifier.
    version : int
        Optimistic concurrency version for the proposal.
    name : str | None
        Proposal name.
    description : str | None
        Proposal description.
    status : ProposalStatus | None
        Proposal status.
    created : str | None
        Creation timestamp.
    updated : str | None
        Update timestamp.
    extras : dict
        Proposal-specific extra fields.
    """

    proposal_id: str
    problem_id: str
    version: int = 0
    name: str | None = None
    description: str | None = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created: str | None = None
    updated: str | None = None
    extras: dict = field(default_factory=dict)

    @classmethod
    def create_default(
        cls,
        proposal_id: str,
        *,
        problem_id: str = "",
        version: int = 1,
        name: str | None = None,
        description: str | None = None,
        status: ProposalStatus | str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
    ) -> Proposal:
        """Create a proposal with default values."""
        now = get_timestamp()
        return cls(
            proposal_id=proposal_id,
            problem_id=problem_id,
            version=version,
            name=proposal_id if name is None else name,
            description=description or "",
            status=_coerce_status(status),
            created=created or now,
            updated=updated or now,
            extras={} if extras is None else extras,
        )

    @classmethod
    def from_dict(cls, data: dict) -> Proposal:
        """Build a proposal from a flat proposal payload dictionary."""
        status = data.get("status")
        return cls(
            proposal_id=data["proposal_id"],
            problem_id=data.get("problem_id", ""),
            version=data.get("version", 0),
            name=data.get("name"),
            description=data.get("description"),
            status=_coerce_status(status),
            created=data.get("created"),
            updated=data.get("updated"),
            extras=data.get("extras", {}),
        )
