# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from fastapi import HTTPException, Response, status
from slugify import slugify

from overtourism.backend.api.shared.exceptions import ProblemNotFound
from overtourism.backend.handler import Handler
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import ProposalStatus
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import values_as_scipy

if typing.TYPE_CHECKING:
    from overtourism.backend.api.v2.models.problem import (
        PostProblemData,
        UpdateProblemData,
    )
    from overtourism.backend.api.v2.models.proposal import Proposal as ProposalModel
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.evaluation.manager import EvaluationManager
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
    except KeyError:
        raise ProblemNotFound(msg)
    if problem.tenant != tenant:
        raise ProblemNotFound(msg)
    return problem


def set_version_header(response: Response, version: int) -> None:
    """Expose the current entity version through a standard ETag header."""
    response.headers["ETag"] = str(version)


def get_session_scenario_or_404(
    handler: Handler,
    problem_id: str,
    session_id: str,
    scenario_id: str,
) -> Scenario:
    """Return an in-memory session scenario or raise a not-found error."""
    detail = f"Scenario '{scenario_id}' not found for problem '{problem_id}' in session '{session_id}'"
    try:
        scenario = handler.manager.read_session_scenario(problem_id, session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail
        ) from exc
    if scenario.scenario_id != scenario_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
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
        evaluation = handler.manager.read_session_evaluation(problem_id, session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail
        ) from exc
    if evaluation.scenario_id != scenario_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return evaluation


def parse_version(version: str | None) -> int | None:
    """Parse a single Version version token into an integer version."""
    if version is None:
        return None
    try:
        parsed_version = int(version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version must contain an integer version",
        ) from exc

    if parsed_version < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version must be a positive integer version",
        )
    return parsed_version


def check_version(current_version: int, version: str | None) -> None:
    """Reject stale or missing Version validators before a write."""
    expected_version = parse_version(version)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Missing Version header",
        )
    if expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                f"Version mismatch: expected {expected_version}, current version is {current_version}"
            ),
        )


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
    return {
        "name": data.problem_name,
        "description": data.problem_description,
        "extras": build_problem_extras(handler, data.model_dump(exclude_unset=True)),
    }


def problem_to_api(problem: Problem) -> dict[str, typing.Any]:
    """Convert a problem entity to the API response shape."""
    return {
        "problem_id": problem.problem_id,
        "version": problem.version,
        "tenant": problem.tenant,
        "name": problem.name,
        "description": problem.description,
        "created": problem.created,
        "updated": problem.updated,
        "extras": dict(problem.extras),
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


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


def parse_proposal_model(
    handler: Handler,
    data: ProposalModel,
) -> dict[str, typing.Any]:
    """Extract proposal extras and related scenario IDs from a payload."""
    extras = handler.manager.proposal_extras_from_dict(
        data.model_dump(exclude_unset=True)
    )
    status = data.status or ProposalStatus.DRAFT
    if not isinstance(status, ProposalStatus):
        status = ProposalStatus(status)
    return {
        "name": data.proposal_title,
        "description": data.proposal_description,
        "status": status,
        "extras": extras,
        "related_scenario_ids": [
            related_scenario.scenario_id for related_scenario in data.related_scenarios
        ],
    }


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


def prepare_values(
    handler: Handler,
    values: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Prepare values for evaluation using the viewer if available."""
    if handler.prepare_values_fn is not None:
        return handler.prepare_values_fn(values)
    return values


def arrange_data(handler: Handler, data: typing.Any) -> dict:
    """Convert model output to API dict using arrange_data_fn if available."""
    if handler.arrange_data_fn is not None:
        return handler.arrange_data_fn(data)
    return data


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, str]:
    """Compute the model index differences for a scenario on demand."""
    return handler.manager.model_evaluator.get_index_diffs(
        handler.manager.model,
        values=values_as_scipy(scenario),
    )


def model_values(handler: Handler) -> dict[str, typing.Any]:
    """Return the base model values exposed by the facade manager."""
    return handler.manager.model_evaluator.get_model_values(handler.manager.model)


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
    return result.to_dict() if hasattr(result, "to_dict") else result
