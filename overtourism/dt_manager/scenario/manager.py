# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import scenario_values
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.utils.exception import (
    ScenarioAlreadyExists,
    ScenarioDoesNotExist,
    SessionDoesNotExist,
)
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model

    from overtourism.dt_manager.classes.model import ModelEvaluator


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
        self.scenarios: dict[str, Scenario] = {}
        self._sessions: dict[str, Scenario] = {}

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
        """Create a new scenario."""
        if scenario_id in self.scenarios:
            raise ScenarioAlreadyExists(
                f"Scenario with ID {scenario_id} already exists"
            )
        self.scenarios[scenario_id] = self._create_scenario(
            scenario_id=scenario_id,
            values=values,
            name=name,
            description=description,
            created=created,
            updated=updated,
            extras=extras,
        )
        return self.scenarios[scenario_id]

    def read_scenario(self, scenario_id: str) -> Scenario:
        """Return a registered scenario."""
        if scenario_id not in self.scenarios:
            raise ScenarioDoesNotExist(f"Scenario with ID {scenario_id} does not exist")
        return self.scenarios[scenario_id]

    def update_scenario(self, scenario_id: str, values: dict) -> None:
        """Update a scenario with new values."""
        if scenario_id not in self.scenarios:
            raise ScenarioDoesNotExist(f"Scenario with ID {scenario_id} does not exist")

        old_scenario = self.scenarios[scenario_id]
        self.scenarios[scenario_id] = scenario_values(
            scenario_id,
            values,
            name=old_scenario.name,
            description=old_scenario.description,
            created=old_scenario.created,
            updated=get_timestamp(),
            extras=old_scenario.extras,
            problem_id=self.problem_id,
        )

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a scenario from memory and storage."""
        try:
            self.scenarios.pop(scenario_id)
        except KeyError:
            raise ScenarioDoesNotExist(f"Scenario with ID {scenario_id} does not exist")
        self.store.delete_scenario(self.problem_id, scenario_id)

    # ───────────────────────────────────────────────────────────
    # I/O
    # ───────────────────────────────────────────────────────────

    def save_scenario(
        self,
        scenario_id: str,
    ) -> Scenario:
        """Persist a scenario to storage."""
        scenario = self.read_scenario(scenario_id)
        scenario.index_values = list(scenario.index_values)
        scenario.problem_id = self.problem_id
        self.store.save_scenario(
            self.problem_id,
            scenario_id,
            scenario.to_dict(),
        )
        return scenario

    def load_scenarios(self) -> list[Scenario]:
        """Load all scenarios for the current problem."""
        return [
            self._build_scenario(scenario_data)
            for scenario_data in self.store.load_scenarios(self.problem_id)
        ]

    def load_scenario(self, scenario_data: Scenario) -> None:
        """Load a scenario into memory."""
        if scenario_data.scenario_id not in self.scenarios:
            self.scenarios[scenario_data.scenario_id] = scenario_data

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

    def _build_scenario(self, scenario_data: dict) -> Scenario:
        return Scenario.from_dict(scenario_data)

    def _create_session_scenario(
        self,
        scenario_id: str,
        values: dict,
    ) -> Scenario:
        """Create a transient scenario used for a session evaluation."""
        origin = self.read_scenario(scenario_id)
        now_timestamp = get_timestamp()
        return self._create_scenario(
            scenario_id=scenario_id,
            values=values,
            name=origin.name,
            description=origin.description,
            created=now_timestamp,
            updated=now_timestamp,
        )

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(
        self,
        scenario_id: str,
        values: dict,
    ) -> Scenario:
        """Create a transient scenario used for a session evaluation."""
        return self._create_session_scenario(scenario_id, values)

    def register_session_scenario(self, session_id: str, scenario: Scenario) -> None:
        """Store a transient scenario under its session identifier."""
        self._sessions[session_id] = scenario

    def read_session_scenario(self, session_id: str) -> Scenario:
        """Return an active session scenario."""
        if session_id not in self._sessions:
            raise SessionDoesNotExist(f"Session '{session_id}' does not exist")
        return self._sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        """Check whether a session is active."""
        return session_id in self._sessions

    def close_session(self, session_id: str) -> None:
        """Close a session and discard its transient scenario."""
        self._sessions.pop(session_id, None)
