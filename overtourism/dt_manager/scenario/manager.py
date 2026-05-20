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
        return self._build_scenario(
            self.store.load_scenario(self.problem_id, scenario_id)
        )

    def list_scenarios(self) -> list[Scenario]:
        """Return all persisted scenarios for the problem."""
        return [
            self._build_scenario(scenario_data)
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
        updated_scenario = scenario_values(
            scenario_id,
            {} if values is None else values,
            name=old_scenario.name if name is None else name,
            description=old_scenario.description
            if description is None
            else description,
            created=old_scenario.created,
            updated=get_timestamp(),
            extras=old_scenario.extras if extras is None else extras,
            problem_id=self.problem_id,
            version=old_scenario.version + 1,
        )
        self.store.save_scenario(
            self.problem_id,
            scenario_id,
            updated_scenario.to_dict(),
        )
        return updated_scenario

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete a persisted scenario."""
        self.read_scenario(scenario_id)
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

    def _build_scenario(self, scenario_data: dict) -> Scenario:
        return Scenario.from_dict(scenario_data)

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

    def _read_registered_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
    ) -> Scenario:
        scenario = self.read_session_scenario(session_id)
        if scenario.scenario_id != scenario_id:
            raise ScenarioDoesNotExist(
                f"Scenario with ID {scenario_id} does not exist in session {session_id}"
            )
        return scenario

    # ───────────────────────────────────────────────────────────
    # Sessions
    # ───────────────────────────────────────────────────────────

    def create_session_scenario(
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
        scenario = self._create_session_scenario(
            session_id,
            scenario_id,
            values,
            name=name,
            description=description,
            extras=extras,
        )
        self._sessions[session_id] = scenario
        return scenario

    def update_session_scenario(
        self,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update an in-memory session scenario."""
        session_scenario = self._read_registered_session_scenario(
            session_id, scenario_id
        )
        updated_scenario = self._update_existing_scenario(
            session_scenario,
            scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        self._sessions[session_id] = updated_scenario
        return updated_scenario

    def save_session_scenario(
        self,
        session_id: str,
        scenario_id: str | None = None,
    ) -> Scenario:
        """Promote a transient session scenario to persistent storage."""
        scenario = (
            self.read_session_scenario(session_id)
            if scenario_id is None
            else self._read_registered_session_scenario(session_id, scenario_id)
        )
        scenario.problem_id = self.problem_id
        self.store.save_scenario(
            self.problem_id,
            scenario.scenario_id,
            scenario.to_dict(),
        )
        return scenario

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
