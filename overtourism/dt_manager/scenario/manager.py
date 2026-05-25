# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import scenario_values, values_as_scipy
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    ScenarioAlreadyExists,
    ScenarioDoesNotExist,
)
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model
    from civic_digital_twins.dt_model.simulation.runner import ModelEvaluator


class ScenarioManager:
    """Manage scenario entities for a single problem."""

    def __init__(
        self,
        problem_id: str,
        model: Model,
        model_evaluator: ModelEvaluator,
        store: Store,
    ) -> None:
        """Create a scenario manager bound to a problem."""
        self.problem_id = problem_id
        self.model = model
        self.model_evaluator = model_evaluator
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_scenario(
        self,
        scenario_id: str,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Create and persist a new scenario."""
        try:
            self.store.load_scenario(self.problem_id, scenario_id)
        except ScenarioDoesNotExist:
            pass
        else:
            raise ScenarioAlreadyExists(
                f"Scenario with ID {scenario_id} already exists"
            )
        scenario = self._create_scenario(
            scenario_id=scenario_id,
            values=values,
            name=name,
            description=description,
            created=created,
            updated=updated,
            extras=extras,
        )
        self.store.save_scenario(self.problem_id, scenario_id, scenario.to_dict())
        return scenario

    def read_scenario(self, scenario_id: str) -> Scenario:
        """Return a persisted scenario."""
        return Scenario.from_dict(
            self.store.load_scenario(self.problem_id, scenario_id)
        )

    def list_scenarios(self) -> list[Scenario]:
        """Return all persisted scenarios for the problem."""
        return [
            Scenario.from_dict(scenario_data)
            for scenario_data in self.store.load_scenarios(self.problem_id)
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
        updated_scenario = self.update_scenario_object(
            old_scenario,
            scenario_id=scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        self.save_scenario_object(updated_scenario)
        return updated_scenario

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a persisted scenario."""
        self.store.delete_scenario(self.problem_id, scenario_id)

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _create_scenario(
        self,
        scenario_id: str,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        created: str | None = None,
        updated: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Build a scenario object from values and metadata."""
        values = {} if values is None else values
        return scenario_values(
            scenario_id,
            values,
            name=name,
            description=description,
            created=created,
            updated=updated,
            extras=extras,
            problem_id=self.problem_id,
        )

    def _create_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Create a transient scenario used for a session evaluation."""
        origin = self.read_scenario(scenario_id)
        now_timestamp = get_timestamp()
        return self._create_scenario(
            scenario_id=f"{scenario_id}_{session_id}_{uuid4().hex}",
            values=values_as_scipy(origin) if values is None else values,
            name=origin.name if name is None else name,
            description=origin.description if description is None else description,
            created=now_timestamp,
            updated=now_timestamp,
            extras=dict(origin.extras) if extras is None else extras,
        )

    def _update_existing_scenario(
        self,
        scenario: Scenario,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        return scenario_values(
            scenario_id,
            values_as_scipy(scenario) if values is None else values,
            name=scenario.name if name is None else name,
            description=scenario.description if description is None else description,
            created=scenario.created,
            updated=get_timestamp(),
            extras=scenario.extras if extras is None else extras,
            problem_id=self.problem_id,
            version=scenario.version + 1,
        )

    def build_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Build a transient scenario draft from a stored scenario."""
        return self._create_session_scenario(
            session_id,
            scenario_id,
            values,
            name=name,
            description=description,
            extras=extras,
        )

    def update_scenario_object(
        self,
        scenario: Scenario,
        *,
        scenario_id: str | None = None,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Return an updated copy of an existing scenario object."""
        target_scenario_id = (
            scenario.scenario_id if scenario_id is None else scenario_id
        )
        return self._update_existing_scenario(
            scenario,
            target_scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )

    def save_scenario_object(self, scenario: Scenario) -> Scenario:
        """Persist a scenario object as-is."""
        self.store.save_scenario(
            self.problem_id,
            scenario.scenario_id,
            scenario.to_dict(),
        )
        return scenario
