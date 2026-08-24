# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from fastapi import HTTPException, status

from overtourism.backend.auth.dependencies import Handler
from overtourism.dt_manager.indexes.index import IndexType
from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
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


def get_problem_or_404(
    tenant: str,
    handler: Handler,
    problem_id: str,
) -> Problem:
    """Return a problem for the requested tenant or raise a not-found error."""
    try:
        return handler.manager.read_problem(problem_id, tenant=tenant)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem '{problem_id}' not found.",
        ) from exc


# ──────────────────────────────────────────────
# Scenario
# ──────────────────────────────────────────────


def get_scenario_or_404(
    tenant: str,
    handler: Handler,
    scenario_id: str,
) -> Scenario:
    """Return a stored scenario or raise a not-found error."""
    try:
        return handler.manager.read_scenario(scenario_id, tenant=tenant)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        ) from exc


def raise_immutable_base_scenario_error(
    handler: Handler,
    tenant: str,
    scenario_id: str,
) -> None:
    """Raise an error indicating that the base scenario cannot be modified."""
    if scenario_id == BootstrapConfig(tenant).scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base scenario cannot be modified or deleted.",
        )


def _scenario_to_index_values(scenario: Scenario) -> list[dict[str, typing.Any]]:
    return [
        {
            "index_name": index_name,
            "index_value": index_value,
            "index_type": IndexType.CONSTANT.value,
        }
        for index_name, index_value in scenario.param_overrides.items()
    ]


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, typing.Any]:
    """Return the current scenario index diffs for API payloads.

    Tests may monkeypatch this hook to inject deterministic values.
    """
    return {}


def scenario_to_api(handler: Handler, scenario: Scenario) -> dict[str, typing.Any]:
    """Convert a scenario entity to the API response shape."""
    payload = scenario.to_dict()
    payload["index_values"] = _scenario_to_index_values(scenario)
    payload["extras"] = {
        **payload.get("extras", {}),
        "index_diffs": scenario_index_diffs(handler, scenario),
    }
    return payload


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


def get_proposal_or_404(
    tenant: str,
    handler: Handler,
    proposal_id: str,
):
    """Return a stored proposal or raise a not-found error."""
    try:
        return handler.manager.read_proposal(proposal_id, tenant=tenant)
    except ProposalDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found.",
        ) from exc


def validate_related_scenario_ids(
    tenant: str,
    handler: Handler,
    related_scenario_ids: list[str] | None,
) -> list[str] | None:
    if related_scenario_ids is None:
        return None
    validated_ids = list(dict.fromkeys(related_scenario_ids))
    for scenario_id in validated_ids:
        get_scenario_or_404(tenant, handler, scenario_id)
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
    tenant: str,
    handler: Handler,
    evaluation_id: str,
) -> Evaluation:
    """Return a stored evaluation by ID or raise a not-found error."""
    detail = f"Evaluation '{evaluation_id}' not found"
    try:
        return handler.manager.read_evaluation(evaluation_id, tenant=tenant)
    except EvaluationDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{detail}.",
        ) from exc


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
            detail=f"Session '{session_id}' not found.",
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
            detail=f"Scenario '{scenario_id}' not found in session '{session_id}'.",
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
            detail=f"Evaluation for scenario '{scenario_id}' not found in session '{session_id}'.",
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
            detail=f"Evaluation '{evaluation_id}' not found in session '{session_id}'.",
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
