# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from fastapi import HTTPException, status
from slugify import slugify

from overtourism.backend.api.shared.exceptions import ProblemNotFound
from overtourism.backend.api.v2.models.evaluation import (
    EvaluationData,
    EvaluationOutputData,
)
from overtourism.backend.api.v2.models.scenario import ScenarioData
from overtourism.backend.api.v2.models.session import SessionData, SessionSummaryData
from overtourism.backend.handler import Handler
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import values_as_scipy
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
    ScenarioDoesNotExist,
)

if typing.TYPE_CHECKING:
    from overtourism.backend.api.v2.models.problem import (
        PostProblemData,
        UpdateProblemData,
    )
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.evaluation.manager import EvaluationManager
    from overtourism.dt_manager.manager.manager import SessionState
    from overtourism.dt_manager.problem.manager import ProblemManager
    from overtourism.dt_manager.proposal.manager import ProposalManager
    from overtourism.dt_manager.scenario.manager import ScenarioManager


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


def get_problem_or_404(
    handler: Handler,
    tenant: str,
    problem_id: str,
) -> Problem:
    """Return a problem for the requested tenant or raise a not-found error."""
    msg = f"Problem '{problem_id}' not found for tenant '{tenant}'"
    try:
        problem = handler.manager.read_problem(problem_id)
    except (FileNotFoundError, KeyError):
        raise ProblemNotFound(msg)
    if problem.tenant != tenant:
        raise ProblemNotFound(msg)
    return problem


def get_scenario_or_404(
    handler: Handler,
    problem_id: str,
    scenario_id: str,
) -> Scenario:
    """Return a stored scenario or raise a not-found error."""
    detail = f"Scenario '{scenario_id}' not found for problem '{problem_id}'"
    try:
        return handler.manager.read_scenario(problem_id, scenario_id)
    except ScenarioDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def get_proposal_or_404(
    handler: Handler,
    problem_id: str,
    proposal_id: str,
):
    """Return a stored proposal or raise a not-found error."""
    detail = f"Proposal '{proposal_id}' not found for problem '{problem_id}'"
    try:
        return handler.manager.read_proposal(problem_id, proposal_id)
    except ProposalDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def get_evaluation_or_404(
    handler: Handler,
    problem_id: str,
    scenario_id: str,
) -> Evaluation:
    """Return the latest stored evaluation or raise a not-found error."""
    detail = (
        f"Evaluation for scenario '{scenario_id}' not found for problem '{problem_id}'"
    )
    try:
        return handler.manager.read_latest_evaluation(problem_id, scenario_id)
    except EvaluationDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def get_evaluation_by_id_or_404(
    handler: Handler,
    problem_id: str,
    evaluation_id: str,
) -> Evaluation:
    """Return a stored evaluation by identifier or raise a not-found error."""
    detail = f"Evaluation '{evaluation_id}' not found for problem '{problem_id}'"
    try:
        return handler.manager.read_evaluation(problem_id, evaluation_id)
    except EvaluationDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def problem_from_model(
    handler: Handler,
    data: PostProblemData,
) -> dict[str, typing.Any]:
    """Extract problem fields and extras from a payload."""
    return {
        "name": data.problem_name,
        "description": data.problem_description,
        "extras": build_problem_extras(handler, data.model_dump(exclude_unset=True)),
    }


def problem_update_from_model(
    handler: Handler,
    data: UpdateProblemData,
) -> dict[str, typing.Any]:
    """Extract problem update fields and extras from a payload."""
    payload = data.model_dump(exclude_unset=True, exclude={"version"})
    return {
        "name": data.problem_name,
        "description": data.problem_description,
        "extras": build_problem_extras(handler, payload),
    }


def build_problem_extras(
    handler: Handler,
    payload: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Build problem extras from a request payload."""
    extras = handler.manager.problem_extras_from_dict(payload)
    extras["editable_indexes"] = get_widget_by_group(handler, payload.get("groups", []))
    return extras


def get_problem_editable_indexes(extras: dict) -> list[str]:
    return [str(item) for item in extras.get("editable_indexes", [])]


def build_evaluation_output(
    handler: Handler,
    scenario: Scenario,
    evaluation: Evaluation,
    *,
    params: list[str] | None = None,
) -> EvaluationOutputData:
    """Build the v2 evaluation output payload for a specific evaluation snapshot."""
    return EvaluationOutputData(
        problem_id=scenario.problem_id,
        scenario_id=scenario.scenario_id,
        evaluation_id=evaluation.evaluation_id,
        data=evaluation_result_to_dict(
            arrange_data(handler, evaluation.result, params=params)
        ),
    )


# ──────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────


def get_widgets(
    handler: Handler,
    values: dict[str, typing.Any],
    language: str = "it",
) -> dict[str, typing.Any] | None:
    """Get widgets from viewer if available, otherwise None."""
    if handler.viewer is not None:
        return handler.viewer.get_widgets(values, language=language)
    return None


def get_widget_by_group(handler: Handler, groups: list[str]) -> list[str]:
    """Get widget IDs by group from the viewer if available."""
    if handler.viewer is not None and groups:
        return handler.viewer.get_widget_ids_by_groups(groups)
    return []


# ──────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────


def prepare_values(
    handler: Handler,
    values: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Prepare values for evaluation using the viewer if available."""
    if handler.prepare_values_fn is not None:
        return handler.prepare_values_fn(values)
    return values


def arrange_data(
    handler: Handler,
    data: typing.Any,
    params: list[str] | None = None,
) -> dict:
    """Convert model output to API dict using arrange_data_fn if available."""
    if handler.arrange_data_fn is not None:
        return handler.arrange_data_fn(data, params)
    return data


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, str]:
    """Compute the model index differences for a scenario on demand."""
    from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

    evaluator = handler.manager.model_evaluator
    raw_values = values_as_scipy(scenario)
    overrides = evaluator._values_to_overrides(handler.manager.model, raw_values)
    cdt_scenario = CDTScenario(handler.manager.model, overrides=overrides)
    return evaluator.get_index_diffs(cdt_scenario)


def model_values(handler: Handler) -> dict[str, typing.Any]:
    """Return the base model values exposed by the facade manager."""
    from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

    cdt_scenario = CDTScenario(handler.manager.model)
    return handler.manager.model_evaluator.get_model_values(cdt_scenario)


# ──────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────


def get_session_scenario_or_404(
    handler: Handler,
    problem_id: str,
    session_id: str,
    scenario_id: str,
) -> Scenario:
    """Return an in-memory session scenario or raise a not-found error."""
    detail = f"Scenario '{scenario_id}' not found for problem '{problem_id}' in session '{session_id}'"
    try:
        scenario = handler.manager.read_session_scenario(
            problem_id,
            session_id,
            scenario_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail
        ) from exc
    return scenario


def get_session_evaluation_or_404(
    handler: Handler,
    problem_id: str,
    session_id: str,
    scenario_id: str,
) -> Evaluation:
    """Return an in-memory session evaluation or raise a not-found error."""
    detail = f"Evaluation for scenario '{scenario_id}' not found for problem '{problem_id}' in session '{session_id}'"
    try:
        evaluation = handler.manager.read_session_evaluation(
            problem_id,
            session_id,
            scenario_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail
        ) from exc
    return evaluation


def get_session_evaluation_by_id_or_404(
    handler: Handler,
    problem_id: str,
    session_id: str,
    evaluation_id: str,
) -> Evaluation:
    """Return an in-memory session evaluation by identifier or raise a not-found error."""
    detail = f"Evaluation '{evaluation_id}' not found for problem '{problem_id}' in session '{session_id}'"
    try:
        return handler.manager.read_session_evaluation_by_id(
            problem_id,
            session_id,
            evaluation_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def get_session_or_404(
    handler: Handler,
    problem_id: str,
    session_id: str,
) -> SessionState:
    """Return an in-memory session or raise a not-found error."""
    detail = f"Session '{session_id}' not found for problem '{problem_id}'"
    try:
        return handler.manager.read_session(problem_id, session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def session_summary_to_api(session) -> SessionSummaryData:
    return SessionSummaryData(
        problem_id=session.problem_id,
        session_id=session.session_id,
        created=session.created,
        updated=session.updated,
        metadata=dict(session.metadata),
        active_scenario_id=session.active_scenario_id,
        draft_ids=list(session.drafts),
    )


def session_to_api(session) -> SessionData:
    return SessionData(
        problem_id=session.problem_id,
        session_id=session.session_id,
        created=session.created,
        updated=session.updated,
        metadata=dict(session.metadata),
        active_scenario_id=session.active_scenario_id,
        draft_ids=list(session.drafts),
        drafts=[
            ScenarioData(**api_entity_payload(draft.to_dict()))
            for draft in session.drafts.values()
        ],
        evaluations={
            scenario_id: EvaluationData(**api_entity_payload(evaluation.to_dict()))
            for scenario_id, evaluation in session.evaluations.items()
        },
    )


def api_entity_payload(payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Expose the persistence payload without renaming its version field."""
    return dict(payload)


def parse_version(version: int | str | None) -> int | None:
    """Parse an incoming concurrency token into an integer version."""
    if version is None:
        return None
    if isinstance(version, int):
        parsed_version = version
    else:
        try:
            parsed_version = int(version)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="version must contain an integer value",
            ) from exc

    if parsed_version < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="version must be a positive integer",
        )
    return parsed_version


def check_version(current_version: int, version: int | str | None) -> None:
    """Reject stale or missing entity versions before a write."""
    expected_version = parse_version(version)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Missing version in entity payload",
        )
    if expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                f"version mismatch: expected {expected_version}, current version is {current_version}"
            ),
        )


# ──────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────


def slugify_name(name: str) -> str:
    """Generate a slugified identifier from a name."""
    return slugify(name)


def problem_manager(handler: Handler, problem_id: str) -> ProblemManager:
    return handler.manager.problem_manager


def proposal_manager(handler: Handler, problem_id: str) -> ProposalManager:
    return handler.manager.proposal_managers[problem_id]


def scenario_manager(handler: Handler, problem_id: str) -> ScenarioManager:
    return handler.manager.scenario_managers[problem_id]


def evaluation_manager(handler: Handler, problem_id: str) -> EvaluationManager:
    return handler.manager.evaluation_managers[problem_id]


def evaluation_result_to_dict(result: typing.Any) -> dict:
    """Normalize a model output or mapping into a plain dictionary."""
    if result is None:
        return {}
    return result.to_snapshot() if hasattr(result, "to_snapshot") else result
