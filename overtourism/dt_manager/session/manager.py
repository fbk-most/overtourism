# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from uuid import uuid4

from overtourism.dt_manager.evaluation.evaluation import DEFAULT_EVALUATION_TYPE
from overtourism.dt_manager.session.session import SessionState
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ScenarioDoesNotExist,
    SessionDoesNotExist,
)
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.simulation.runner import ModelOutput

    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.evaluation.manager import EvaluationManager
    from overtourism.dt_manager.problem.manager import ProblemManager
    from overtourism.dt_manager.scenario.manager import ScenarioManager
    from overtourism.dt_manager.scenario.scenario import Scenario


class SessionManager:
    """Own transient session state and the draft/evaluation workflow."""

    def __init__(
        self,
        problem_manager: ProblemManager,
        scenario_managers: dict[str, ScenarioManager],
        evaluation_managers: dict[str, EvaluationManager],
    ) -> None:
        self.problem_manager = problem_manager
        self.scenario_managers = scenario_managers
        self.evaluation_managers = evaluation_managers
        self.sessions: dict[tuple[str, str], SessionState] = {}

    def delete_problem_sessions(self, problem_id: str) -> None:
        """Discard every transient session associated with a problem."""
        self.sessions = {
            key: session
            for key, session in self.sessions.items()
            if key[0] != problem_id
        }

    def create_session(
        self,
        problem_id: str,
        session_id: str,
        metadata: dict | None = None,
    ) -> SessionState:
        """Create an in-memory session state for a problem."""
        self.problem_manager.read_problem(problem_id)
        key = (problem_id, session_id)
        if key in self.sessions:
            raise ValueError(
                f"Session '{session_id}' already exists for problem '{problem_id}'"
            )
        now_timestamp = get_timestamp()
        session = SessionState(
            session_id=session_id,
            problem_id=problem_id,
            created=now_timestamp,
            updated=now_timestamp,
            metadata={} if metadata is None else dict(metadata),
        )
        self.sessions[key] = session
        return session

    def read_session(self, problem_id: str, session_id: str) -> SessionState:
        """Return an in-memory session state."""
        return self._read_session_state(problem_id, session_id)

    def list_sessions(self, problem_id: str) -> list[SessionState]:
        """Return all in-memory sessions for a problem."""
        return [
            session
            for (session_problem_id, _session_id), session in self.sessions.items()
            if session_problem_id == problem_id
        ]

    def has_session(self, problem_id: str, session_id: str) -> bool:
        """Return whether a session exists for the problem."""
        return (problem_id, session_id) in self.sessions

    def delete_session(self, problem_id: str, session_id: str) -> None:
        """Delete an in-memory session and all its drafts/evaluations."""
        self._read_session_state(problem_id, session_id)
        self.sessions.pop((problem_id, session_id), None)

    def create_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        *,
        values: dict | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Create a transient scenario for a session."""
        session = self.sessions.get((problem_id, session_id))
        if session is None:
            session = self.create_session(problem_id, session_id)
        scenario = self.scenario_managers[problem_id].build_session_scenario(
            session_id,
            scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        session.drafts[scenario.scenario_id] = scenario
        session.active_scenario_id = scenario.scenario_id
        session.updated = get_timestamp()
        return scenario

    def list_session_scenarios(
        self,
        problem_id: str,
        session_id: str,
    ) -> list[Scenario]:
        """Return all drafts stored in a session."""
        return list(self._read_session_state(problem_id, session_id).drafts.values())

    def update_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        values: dict | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Scenario:
        """Update a transient session scenario and invalidate its evaluation."""
        session = self._read_session_state(problem_id, session_id)
        session_scenario = self._read_session_draft(
            session,
            scenario_id,
        )
        updated_scenario = self.scenario_managers[problem_id].update_scenario_object(
            session_scenario,
            scenario_id=session_scenario.scenario_id,
            values=values,
            name=name,
            description=description,
            extras=extras,
        )
        session.drafts[updated_scenario.scenario_id] = updated_scenario
        session.evaluations.pop(updated_scenario.scenario_id, None)
        session.active_scenario_id = updated_scenario.scenario_id
        session.updated = get_timestamp()
        return updated_scenario

    def delete_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
    ) -> None:
        """Delete a draft scenario and its evaluation from a session."""
        session = self._read_session_state(problem_id, session_id)
        self._read_session_draft(session, scenario_id)
        self._drop_session_draft_state(session, scenario_id)

    def read_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str | None = None,
    ) -> Scenario:
        """Return a transient scenario for a session."""
        session = self._read_session_state(problem_id, session_id)
        return self._read_session_draft(session, scenario_id)

    def read_session_evaluation(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str | None = None,
    ) -> Evaluation:
        """Return the transient evaluation attached to a session."""
        session = self._read_session_state(problem_id, session_id)
        return self._read_session_draft_evaluation(session, scenario_id)

    def resume_session(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str | None = None,
    ) -> tuple[Scenario, Evaluation]:
        """Return the transient session scenario and its evaluation."""
        return (
            self.read_session_scenario(problem_id, session_id, scenario_id),
            self.read_session_evaluation(problem_id, session_id, scenario_id),
        )

    def save_session_scenario(
        self,
        problem_id: str,
        session_id: str,
        *,
        scenario_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
        proposal_id: str | None = None,
    ) -> Scenario:
        """Promote a transient session scenario to persistent storage."""
        session = self._read_session_state(problem_id, session_id)
        session_scenario = self._read_session_draft(session, scenario_id)

        if name is not None:
            session_scenario.name = name
        if description is not None:
            session_scenario.description = description
        if extras is not None:
            session_scenario.extras.update(extras)

        self.scenario_managers[problem_id].save_scenario_object(session_scenario)
        try:
            session_evaluation = self._read_session_draft_evaluation(
                session,
                session_scenario.scenario_id,
            )
        except EvaluationDoesNotExist:
            pass
        else:
            self.evaluation_managers[problem_id].save_evaluation(session_evaluation)

        if proposal_id is not None:
            self.problem_manager.link_scenario_proposal(
                problem_id,
                proposal_id,
                session_scenario.scenario_id,
            )

        self._drop_session_draft_state(session, session_scenario.scenario_id)
        return session_scenario

    def close_session(self, problem_id: str, session_id: str) -> None:
        """Close a session and discard both scenario and evaluation state."""
        self.delete_session(problem_id, session_id)

    def evaluate_session(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        values: dict,
        **kwargs,
    ) -> Scenario:
        """Evaluate a transient session scenario and keep both states in memory."""
        session_scenario = self.create_session_scenario(
            problem_id,
            session_id,
            scenario_id,
            values=values,
        )
        self.create_session_evaluation(
            problem_id,
            session_id,
            session_scenario.scenario_id,
            **kwargs,
        )
        return session_scenario

    def create_session_evaluation(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str,
        **kwargs,
    ) -> Evaluation:
        """Evaluate an existing transient session scenario."""
        session = self._read_session_state(problem_id, session_id)
        scenario = self._read_session_draft(session, scenario_id)
        evaluation_manager = self.evaluation_managers[problem_id]
        session.evaluations.pop(scenario.scenario_id, None)
        evaluation_id = f"{scenario.scenario_id}_{uuid4().hex}"
        evaluation = evaluation_manager.build_running_evaluation(
            evaluation_id,
            scenario_id=scenario.scenario_id,
            type=DEFAULT_EVALUATION_TYPE,
        )
        evaluation = evaluation_manager.execute_evaluation(
            evaluation,
            scenario,
            **kwargs,
        )
        session.evaluations[scenario.scenario_id] = evaluation
        session.active_scenario_id = scenario.scenario_id
        session.updated = get_timestamp()
        return evaluation

    def read_session_scenario_data(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str | None = None,
    ) -> ModelOutput:
        """Return the latest in-memory evaluation result for a session draft."""
        return self.read_session_evaluation(problem_id, session_id, scenario_id).result

    def list_session_evaluations(
        self,
        problem_id: str,
        session_id: str,
        scenario_id: str | None = None,
    ) -> list[Evaluation]:
        """Return in-memory evaluations for a session."""
        session = self._read_session_state(problem_id, session_id)
        evaluations = list(session.evaluations.values())
        if scenario_id is None:
            return evaluations
        return [
            evaluation
            for evaluation in evaluations
            if evaluation.scenario_id == scenario_id
        ]

    def read_session_evaluation_by_id(
        self,
        problem_id: str,
        session_id: str,
        evaluation_id: str,
    ) -> Evaluation:
        """Return an in-memory evaluation by identifier."""
        session = self._read_session_state(problem_id, session_id)
        for evaluation in session.evaluations.values():
            if evaluation.evaluation_id == evaluation_id:
                return evaluation
        raise EvaluationDoesNotExist(
            f"Evaluation '{evaluation_id}' does not exist in session '{session_id}'"
        )

    def update_session_evaluation(
        self,
        problem_id: str,
        session_id: str,
        evaluation_id: str,
        ensemble_size: int = 20,
        **kwargs,
    ) -> Evaluation:
        """Re-run an in-memory evaluation for its current draft scenario."""
        session = self._read_session_state(problem_id, session_id)
        evaluation = self.read_session_evaluation_by_id(
            problem_id,
            session_id,
            evaluation_id,
        )
        scenario = self._read_session_draft(session, evaluation.scenario_id)
        updated = self.evaluation_managers[problem_id].rerun_evaluation_object(
            evaluation,
            scenario,
            ensemble_size=ensemble_size,
            **kwargs,
        )
        session.evaluations[scenario.scenario_id] = updated
        session.active_scenario_id = scenario.scenario_id
        session.updated = get_timestamp()
        return updated

    def delete_session_evaluation(
        self,
        problem_id: str,
        session_id: str,
        evaluation_id: str,
    ) -> None:
        """Delete an in-memory evaluation by identifier."""
        session = self._read_session_state(problem_id, session_id)
        evaluation = self.read_session_evaluation_by_id(
            problem_id,
            session_id,
            evaluation_id,
        )
        session.evaluations.pop(evaluation.scenario_id, None)
        session.updated = get_timestamp()

    def _read_session_state(self, problem_id: str, session_id: str) -> SessionState:
        key = (problem_id, session_id)
        if key not in self.sessions:
            raise SessionDoesNotExist(f"Session '{session_id}' does not exist")
        return self.sessions[key]

    def _read_session_draft(
        self,
        session: SessionState,
        scenario_id: str | None = None,
    ) -> Scenario:
        target_scenario_id = scenario_id
        if target_scenario_id is None:
            target_scenario_id = session.active_scenario_id
            if target_scenario_id is None and len(session.drafts) == 1:
                target_scenario_id = next(iter(session.drafts))
        if target_scenario_id is None:
            raise ScenarioDoesNotExist(
                f"Session '{session.session_id}' does not contain an active draft"
            )
        if target_scenario_id not in session.drafts:
            raise ScenarioDoesNotExist(
                f"Scenario with ID {target_scenario_id} does not exist in session {session.session_id}"
            )
        return session.drafts[target_scenario_id]

    def _read_session_draft_evaluation(
        self,
        session: SessionState,
        scenario_id: str | None = None,
    ) -> Evaluation:
        target_scenario_id = scenario_id
        if target_scenario_id is None:
            target_scenario_id = session.active_scenario_id
            if target_scenario_id is None and len(session.evaluations) == 1:
                target_scenario_id = next(iter(session.evaluations))
        if target_scenario_id is None:
            raise EvaluationDoesNotExist(
                f"Session '{session.session_id}' does not contain an active evaluation"
            )
        if target_scenario_id not in session.evaluations:
            raise EvaluationDoesNotExist(
                f"Evaluation for scenario {target_scenario_id} does not exist in session {session.session_id}"
            )
        return session.evaluations[target_scenario_id]

    def _drop_session_draft_state(
        self,
        session: SessionState,
        scenario_id: str,
    ) -> None:
        session.drafts.pop(scenario_id, None)
        session.evaluations.pop(scenario_id, None)
        session.active_scenario_id = next(iter(session.drafts), None)
        session.updated = get_timestamp()
