# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field

from overtourism.dt_manager.classes.dictable import Dictable
from overtourism.dt_manager.utils.utils import get_timestamp


@dataclass
class Problem(Dictable):
    """Domain entity for a problem.

    Parameters
    ----------
    problem_id : str
        Problem identifier.
    name : str | None
        Problem name.
    description : str | None
        Problem description.
    created : str | None
        Creation timestamp.
    updated : str | None
        Update timestamp.
    extras : dict
        Problem-specific extra fields.
    """

    problem_id: str
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    extras: dict = field(default_factory=dict)

    @classmethod
    def create_default(
        cls,
        problem_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
    ) -> Problem:
        """Create a problem with default values."""
        now = get_timestamp()
        return cls(
            problem_id=problem_id,
            name=problem_id if name is None else name,
            description=f"{problem_id} problem" if description is None else description,
            created=now if created is None else created,
            updated=now if updated is None else updated,
            extras={} if extras is None else extras,
        )

    @classmethod
    def from_dict(cls, data: dict) -> Problem:
        """Build a problem from a flat problem payload dictionary."""
        return cls(
            problem_id=data["problem_id"],
            name=data.get("name"),
            description=data.get("description"),
            created=data.get("created"),
            updated=data.get("updated"),
            extras=data.get("extras", {}),
        )
