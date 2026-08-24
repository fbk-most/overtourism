# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from uuid import uuid4

from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    ScenarioAlreadyExists,
)
from overtourism.dt_manager.utils.utils import get_timestamp


class ScenarioManager:
    """Manage scenario entities for a single problem."""

    def __init__(self, store: Store) -> None:
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_scenario(
        self,
        scenario_id: str,
        tenant: str,
        param_overrides: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Create and persist a new scenario."""
        try:
            self.store.load_scenario(scenario_id)
        except EntityDoesNotExist:
            pass
        else:
            raise ScenarioAlreadyExists(
                f"Scenario with ID {scenario_id} already exists"
            )
        scenario = Scenario.create_default(
            scenario_id=scenario_id,
            tenant=tenant,
            param_overrides=param_overrides,
            name=name,
            description=description,
            created=created,
            updated=updated,
            extras=extras,
        )
        self.store.save_scenario(scenario.to_dict())
        return scenario

    def detach_scenario(
        self, scenario_id: str, param_overrides: dict | None = None
    ) -> Scenario:
        """Build a transient scenario draft from a stored scenario."""
        origin = self.read_scenario(scenario_id)
        now_timestamp = get_timestamp()
        return Scenario.create_default(
            scenario_id=uuid4().hex,
            param_overrides=param_overrides,
            name=origin.name,
            description=origin.description,
            created=now_timestamp,
            updated=now_timestamp,
            extras=origin.extras,
            tenant=origin.tenant,
        )

    def read_scenario(self, scenario_id: str, tenant: str | None = None) -> Scenario:
        """Return a persisted scenario."""
        return Scenario.from_dict(self.store.load_scenario(scenario_id, tenant=tenant))

    def list_scenarios(
        self,
        tenant: str | None = None,
        proposal_id: str | None = None,
    ) -> list[Scenario]:
        """Return all persisted scenarios."""
        return [
            Scenario.from_dict(scenario_data)
            for scenario_data in self.store.load_scenarios(
                tenant=tenant,
                proposal_id=proposal_id,
            )
        ]

    def update_scenario(
        self,
        scenario_id: str,
        param_overrides: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a persisted scenario with new values."""
        old_scenario = self.read_scenario(scenario_id)
        scenario = Scenario.create_default(
            scenario_id=scenario_id,
            param_overrides={**old_scenario.param_overrides, **(param_overrides or {})},
            name=name if name is not None else old_scenario.name,
            description=description
            if description is not None
            else old_scenario.description,
            created=old_scenario.created,
            updated=get_timestamp(),
            extras=extras if extras is not None else old_scenario.extras,
            tenant=old_scenario.tenant,
        )
        self.store.save_scenario(scenario.to_dict())
        return scenario

    def update_detached_scenario(
        self,
        old_scenario: Scenario,
        param_overrides: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a detached scenario with new values."""
        return Scenario.create_default(
            scenario_id=old_scenario.scenario_id,
            param_overrides={**old_scenario.param_overrides, **(param_overrides or {})},
            name=name if name is not None else old_scenario.name,
            description=description
            if description is not None
            else old_scenario.description,
            created=old_scenario.created,
            updated=get_timestamp(),
            extras=extras if extras is not None else old_scenario.extras,
            tenant=old_scenario.tenant,
        )

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a persisted scenario."""
        self.store.delete_scenario(scenario_id)
