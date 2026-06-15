# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field

from overtourism.dt_manager.indexes.index import IndexEntry
from overtourism.dt_manager.utils.dictable import Dictable
from overtourism.dt_manager.utils.utils import get_timestamp


@dataclass
class Scenario(Dictable):
    """Domain entity for a scenario."""

    scenario_id: str
    tenant: str
    version: int = 0
    name: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    extras: dict = field(default_factory=dict)
    index_values: list[IndexEntry] = field(default_factory=list)

    @classmethod
    def create_default(
        cls,
        scenario_id: str,
        tenant: str,
        *,
        version: int = 1,
        name: str | None = None,
        description: str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
        index_values: list[IndexEntry] | None = None,
    ) -> Scenario:
        """Create a scenario with default values."""
        now = get_timestamp()
        return cls(
            scenario_id=scenario_id,
            tenant=tenant,
            version=version,
            name=scenario_id if name is None else name,
            description=f"{scenario_id} scenario"
            if description is None
            else description,
            created=now if created is None else created,
            updated=now if updated is None else updated,
            extras={} if extras is None else extras,
            index_values=[] if index_values is None else index_values,
        )

    @classmethod
    def from_dict(cls, scenario_dict: dict) -> Scenario:
        """Build a scenario from a flat scenario payload dictionary."""
        created = scenario_dict.get("created") or get_timestamp()
        updated = scenario_dict.get("updated") or created
        return cls(
            scenario_id=scenario_dict["scenario_id"],
            tenant=scenario_dict["tenant"],
            version=scenario_dict.get("version", 0),
            name=scenario_dict.get("name"),
            description=scenario_dict.get("description"),
            created=created,
            updated=updated,
            extras=scenario_dict.get("extras", {}),
            index_values=[
                IndexEntry.from_dict(item)
                for item in scenario_dict.get("index_values", [])
            ],
        )
