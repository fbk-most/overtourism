# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field

from overtourism.dt_manager.classes.dictable import Dictable
from overtourism.dt_manager.classes.indexes import IndexEntry
from overtourism.dt_manager.utils.utils import get_timestamp


@dataclass
class Scenario(Dictable):
    """Domain entity for a scenario.

    The model is always the base model owned by the ScenarioManager.
    Scenario stores overridden values.

    Parameters
    ----------
    scenario_id : str
        Scenario identifier.
    problem_id : str
        Parent problem identifier.
    version : int
        Optimistic concurrency version for the scenario.
    name : str | None
        Scenario name.
    description : str | None
        Scenario description.
    created : str | None
        Creation timestamp.
    updated : str | None
        Update timestamp.
    extras : dict
        Scenario-specific extra fields.
    index_values : list[IndexEntry], optional
        Stored model index values.
    """

    scenario_id: str
    problem_id: str
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
        *,
        problem_id: str = "",
        version: int = 0,
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
            problem_id=problem_id,
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
            problem_id=scenario_dict.get("problem_id", ""),
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
