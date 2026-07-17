# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from fastapi import HTTPException, status

from overtourism.backend.handler import Handler
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import values_as_scipy
from overtourism.dt_manager.utils.exception import (
    EntityDoesNotExist,
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
)

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.session.session import SessionState


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


def get_problem_or_404(handler: Handler, problem_id: str) -> Problem:
    """Return a problem for the requested tenant or raise a not-found error."""
    try:
        return handler.manager.read_problem(problem_id)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem '{problem_id}' not found",
        ) from exc


# ──────────────────────────────────────────────
# Scenario
# ──────────────────────────────────────────────


def get_scenario_or_404(handler: Handler, scenario_id: str) -> Scenario:
    """Return a stored scenario or raise a not-found error."""
    try:
        return handler.manager.read_scenario(scenario_id)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        ) from exc


def raise_immutable_base_scenario_error(
    handler: Handler, tenant: str, scenario_id: str
) -> None:
    """Raise an error indicating that the base scenario cannot be modified."""
    base_scenario_id = handler.manager.scenario_manager.get_base_scenario_id(tenant)
    if scenario_id == base_scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base scenario cannot be modified or deleted",
        )


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


def get_proposal_or_404(handler: Handler, proposal_id: str):
    """Return a stored proposal or raise a not-found error."""
    try:
        return handler.manager.read_proposal(proposal_id)
    except ProposalDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found",
        ) from exc


def validate_related_scenario_ids(
    handler: Handler,
    related_scenario_ids: list[str] | None,
) -> list[str] | None:
    if related_scenario_ids is None:
        return None
    validated_ids = list(dict.fromkeys(related_scenario_ids))
    for scenario_id in validated_ids:
        get_scenario_or_404(handler, scenario_id)
    return validated_ids


def proposal_to_api(
    handler: Handler,
    proposal: Proposal,
) -> dict:
    payload = proposal.to_dict()
    payload["related_scenario_ids"] = (
        handler.manager.relationship_manager.get_related_scenario_ids(
            proposal.proposal_id
        )
    )
    return payload


# ──────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────


def get_evaluation_or_404(
    handler: Handler,
    evaluation_id: str,
) -> Evaluation:
    """Return a stored evaluation by ID or raise a not-found error."""
    detail = f"Evaluation '{evaluation_id}' not found"
    try:
        return handler.manager.read_evaluation(evaluation_id)
    except EvaluationDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


# ──────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────


def get_widgets(
    handler: Handler,
    values: dict[str, typing.Any],
    language: str = "it",
) -> dict[str, typing.Any] | None:
    """Get widgets from viewer if available, otherwise None."""
    if handler.get_widgets_fn is not None:
        return handler.get_widgets_fn(values, language=language)
    if handler.viewer is not None:
        return handler.viewer.get_widgets(values, language=language)
    return None


def get_widget_by_group(handler: Handler, groups: list[str]) -> list[str]:
    """Get widget IDs by group from the viewer if available."""
    if handler.get_widget_ids_by_groups_fn is not None and groups:
        return handler.get_widget_ids_by_groups_fn(groups)
    if handler.viewer is not None and groups:
        return handler.viewer.get_widget_ids_by_groups(groups)
    return []


# ──────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────


def prepare_values(
    handler: Handler,
    values: dict[str, typing.Any] | None,
) -> dict[str, typing.Any] | None:
    """Prepare values for evaluation using the viewer if available."""
    if values is None:
        return
    if handler.prepare_values_fn is not None:
        return handler.prepare_values_fn(values)
    return values


def arrange_data(
    handler: Handler,
    data: typing.Any,
    as_snapshot: bool = True,
    params: list[str] | None = None,
) -> dict:
    """Convert model output to API dict using arrange_data_fn if available."""
    if handler.arrange_data_fn is not None:
        return handler.arrange_data_fn(
            data,
            as_snapshot=as_snapshot,
            params=params,
        )
    return data


def scenario_to_api(handler: Handler, scenario: Scenario) -> dict[str, typing.Any]:
    """Convert a scenario entity to the API response shape."""
    payload = scenario.to_dict()
    payload["extras"] = {
        **payload.get("extras", {}),
        "index_diffs": scenario_index_diffs(handler, scenario),
    }
    return payload


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, str]:
    """Compute the model index differences for a scenario on demand."""
    from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

    evaluator = handler.manager.scenario_manager.model_evaluator
    raw_values = values_as_scipy(scenario)
    overrides = evaluator._values_to_overrides(
        handler.manager.scenario_manager.model, raw_values
    )
    cdt_scenario = CDTScenario(
        handler.manager.scenario_manager.model, overrides=overrides
    )
    return evaluator.get_index_diffs(cdt_scenario)


def model_values(handler: Handler) -> dict[str, typing.Any]:
    """Return the base model values exposed by the facade manager."""
    from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

    cdt_scenario = CDTScenario(handler.manager.scenario_manager.model)
    return handler.manager.scenario_manager.model_evaluator.get_model_values(
        cdt_scenario
    )


# ──────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────


def get_session_or_404(
    handler: Handler,
    session_id: str,
) -> SessionState:
    """Return an in-memory session or raise a not-found error."""
    try:
        return handler.manager.read_session(session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        ) from exc


def get_session_scenario_or_404(
    handler: Handler,
    session_id: str,
    scenario_id: str,
) -> Scenario:
    """Return an in-memory session scenario or raise a not-found error."""
    try:
        return handler.manager.read_session_scenario(
            session_id,
            scenario_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found in session '{session_id}'",
        ) from exc


def get_session_evaluation_or_404(
    handler: Handler,
    session_id: str,
    scenario_id: str,
) -> Evaluation:
    """Return an in-memory session evaluation or raise a not-found error."""
    try:
        return handler.manager.read_session_evaluation(
            session_id,
            scenario_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation for scenario '{scenario_id}' not found in session '{session_id}'",
        ) from exc


def get_session_evaluation_by_id_or_404(
    handler: Handler,
    session_id: str,
    evaluation_id: str,
) -> Evaluation:
    """Return an in-memory session evaluation or raise a not-found error."""
    try:
        return handler.manager.read_session_evaluation_by_id(
            session_id,
            evaluation_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation '{evaluation_id}' not found in session '{session_id}'",
        ) from exc


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────


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
