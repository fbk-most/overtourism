# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import scenario_values, values_as_scipy
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    ScenarioAlreadyExists,
)
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model
    from civic_digital_twins.dt_model.simulation.runner import ModelEvaluator


class ScenarioManager:
    """Manage scenario entities for a single problem."""

    def __init__(
        self,
        model: Model,
        model_evaluator: ModelEvaluator,
        store: Store,
    ) -> None:
        """Create a scenario manager bound to a problem."""
        self.model = model
        self.model_evaluator = model_evaluator
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_scenario(
        self,
        scenario_id: str,
        tenant: str,
        values: dict | None = None,
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
        values = {} if values is None else values
        scenario = scenario_values(
            scenario_id=scenario_id,
            tenant=tenant,
            values=values,
            name=name,
            description=description,
            created=created,
            updated=updated,
            extras=extras,
        )
        self.store.save_scenario(scenario.to_dict())
        return scenario

    def detach_scenario(self, scenario_id: str, values: dict | None = None) -> Scenario:
        """Build a transient scenario draft from a stored scenario."""
        origin = self.read_scenario(scenario_id)
        now_timestamp = get_timestamp()
        return scenario_values(
            scenario_id=uuid4().hex,
            values=_merge_values(values_as_scipy(origin), values),
            name=origin.name,
            description=origin.description,
            created=now_timestamp,
            updated=now_timestamp,
            extras=dict(origin.extras),
            tenant=origin.tenant,
        )

    def read_scenario(self, scenario_id: str) -> Scenario:
        """Return a persisted scenario."""
        return Scenario.from_dict(self.store.load_scenario(scenario_id))

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
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a persisted scenario with new values."""
        old_scenario = self.read_scenario(scenario_id)
        scenario = scenario_values(
            scenario_id,
            values=_merge_values(values_as_scipy(old_scenario), values),
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
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a detached scenario with new values."""
        return scenario_values(
            old_scenario.scenario_id,
            values=_merge_values(values_as_scipy(old_scenario), values),
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


def _merge_values(current_values: dict, new_values: dict | None) -> dict:
    if new_values is None:
        return current_values
    return {**current_values, **new_values}
