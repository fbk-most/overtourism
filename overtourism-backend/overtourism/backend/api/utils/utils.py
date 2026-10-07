# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from collections.abc import Sequence

import requests
from fastapi import HTTPException, status

from overtourism.backend.handler import Handler
from overtourism.backend.utils.executor_utils import call_index_diffs
from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.utils.exception import EntityDoesNotExist

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.evaluation.evaluation import Evaluation
    from overtourism.dt_manager.session.session import Session


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


def get_problem_or_404(
    territory: str,
    handler: Handler,
    problem_id: str,
) -> Problem:
    """Return a problem for the requested territory or raise a not-found error."""
    try:
        return handler.manager.read_problem(problem_id, territory=territory)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem '{problem_id}' not found.",
        ) from exc


# ──────────────────────────────────────────────
# Scenario
# ──────────────────────────────────────────────


def get_scenario_or_404(
    territory: str,
    handler: Handler,
    scenario_id: str,
) -> Scenario:
    """Return a stored scenario or raise a not-found error."""
    try:
        return handler.manager.read_scenario(scenario_id, territory=territory)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        ) from exc


def raise_immutable_base_scenario_error(
    handler: Handler,
    territory: str,
    scenario_id: str,
) -> None:
    """Raise an error indicating that the base scenario cannot be modified."""
    if scenario_id == BootstrapConfig(territory).scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base scenario cannot be modified or deleted.",
        )


def scenario_index_diffs(
    scenarios: Sequence[Scenario],
) -> dict[str, dict[str, str]]:
    """Return parameter diffs grouped into one request per territory."""
    overrides_by_territory: dict[str, dict[str, dict[str, typing.Any]]] = {}
    for scenario in scenarios:
        if scenario.param_overrides:
            overrides_by_territory.setdefault(scenario.territory, {})[
                scenario.scenario_id
            ] = dict(scenario.param_overrides)

    index_diffs_by_scenario: dict[str, dict[str, str]] = {}
    for territory, overrides_by_scenario in overrides_by_territory.items():
        try:
            index_diffs_by_scenario.update(
                call_index_diffs(territory, overrides_by_scenario)
            )
        except requests.RequestException:
            continue
    return index_diffs_by_scenario


def _scenario_to_api(
    scenario: Scenario,
    index_diffs: dict[str, str],
) -> dict[str, typing.Any]:
    payload = scenario.to_dict()
    payload["param_overrides"] = dict(scenario.param_overrides)
    payload["extras"] = {
        **payload.get("extras", {}),
        "index_diffs": index_diffs,
    }
    return payload


def scenarios_to_api(scenarios: Sequence[Scenario]) -> list[dict[str, typing.Any]]:
    """Convert scenarios to API payloads after resolving diffs in batches."""
    index_diffs_by_scenario = scenario_index_diffs(scenarios)
    return [
        _scenario_to_api(
            scenario,
            index_diffs_by_scenario.get(scenario.scenario_id, {}),
        )
        for scenario in scenarios
    ]


def scenario_to_api(scenario: Scenario) -> dict[str, typing.Any]:
    """Convert one scenario using the same batched diff path as scenario lists."""
    return scenarios_to_api([scenario])[0]


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


def get_proposal_or_404(
    territory: str,
    handler: Handler,
    proposal_id: str,
):
    """Return a stored proposal or raise a not-found error."""
    try:
        return handler.manager.read_proposal(proposal_id, territory=territory)
    except EntityDoesNotExist as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found.",
        ) from exc


def validate_related_scenario_ids(
    territory: str,
    handler: Handler,
    related_scenario_ids: list[str] | None,
) -> list[str] | None:
    if related_scenario_ids is None:
        return None
    validated_ids = list(dict.fromkeys(related_scenario_ids))
    for scenario_id in validated_ids:
        get_scenario_or_404(territory, handler, scenario_id)
    return validated_ids


def ensure_base_scenario_id(
    territory: str,
    related_scenario_ids: list[str] | None,
) -> list[str]:
    """Include the territory's base scenario in a new proposal's links."""
    scenario_ids = list(related_scenario_ids or [])
    base_scenario_id = BootstrapConfig(territory).scenario_id
    if base_scenario_id not in scenario_ids:
        scenario_ids.append(base_scenario_id)
    return scenario_ids


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
    territory: str,
    handler: Handler,
    evaluation_id: str,
) -> Evaluation:
    """Return a stored evaluation by ID or raise a not-found error."""
    detail = f"Evaluation '{evaluation_id}' not found"
    try:
        return handler.manager.read_evaluation(evaluation_id, territory=territory)
    except EntityDoesNotExist as exc:
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
) -> Session:
    """Return an in-memory session or raise a not-found error."""
    try:
        return handler.manager.read_session(session_id)
    except EntityDoesNotExist as exc:
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
    except EntityDoesNotExist as exc:
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
    except EntityDoesNotExist as exc:
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
    except EntityDoesNotExist as exc:
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
