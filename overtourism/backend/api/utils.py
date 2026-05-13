# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from overtourism.backend.api.shared.exceptions import ProblemNotFound
from overtourism.backend.api.shared.problem_metadata import (
    EDITABLE_INDEXES_KEY,
    get_problem_editable_indexes,
    set_problem_editable_indexes,
    with_problem_editable_indexes,
)
from overtourism.backend.handler import Handler
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import values_as_scipy


def get_problem_or_404(handler: Handler, problem_id: str) -> Problem:
    """Return a problem or raise a not-found error."""
    try:
        return handler.manager.read_problem(problem_id)
    except KeyError:
        raise ProblemNotFound(f"Problem '{problem_id}' not found")


def get_widget_by_group(handler: Handler, groups: list[str]) -> list[str]:
    """Get widget IDs by group from the viewer if available."""
    if handler.viewer is not None and groups:
        return handler.viewer.get_widget_ids_by_groups(groups)
    return []


def get_scenario_map(handler: Handler, problem_id: str) -> dict[str, Scenario]:
    """Return the currently loaded scenarios indexed by scenario id."""
    return {
        scenario.scenario_id: scenario
        for scenario in handler.manager.list_scenarios(problem_id)
    }


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, str]:
    """Compute the model index differences for a scenario on demand."""
    return handler.manager.model_evaluator.get_index_diffs(
        handler.manager.model,
        values=values_as_scipy(scenario),
    )


def build_problem_extras(
    handler: Handler,
    payload: dict,
    editable_indexes: list[str] | None = None,
) -> dict:
    """Build problem extras from a request payload."""
    extras: dict = {}
    if handler.manager.extras_config is not None:
        extras = handler.manager.extras_config.problem_extras_from_dict(payload)
    return with_problem_editable_indexes(extras, editable_indexes)


def apply_problem_request_to_metadata(
    handler: Handler,
    problem: Problem,
    payload: dict,
) -> None:
    """Apply a problem update payload to an existing problem."""
    if payload.get("problem_name") is not None:
        problem.name = payload["problem_name"]
    if payload.get("problem_description") is not None:
        problem.description = payload["problem_description"]
    if payload.get("editable_indexes") is not None:
        set_problem_editable_indexes(problem.extras, payload["editable_indexes"])
    if payload.get("groups") is not None:
        editable_indexes = get_widget_by_group(handler, payload["groups"])
        set_problem_editable_indexes(problem.extras, editable_indexes)
        problem.extras["groups"] = payload["groups"]
    if payload.get("objective") is not None:
        problem.extras["objective"] = payload["objective"]
    if payload.get("links") is not None:
        problem.extras["links"] = payload["links"]


def extract_related_scenario_ids(payload: dict) -> list[str]:
    """Normalize related_scenarios entries into unique scenario IDs."""
    related_scenarios = payload.get("related_scenarios") or []
    return list(
        dict.fromkeys(
            scenario["scenario_id"]
            for scenario in related_scenarios
            if scenario.get("scenario_id")
        )
    )


def build_proposal_extras(
    handler: Handler,
    payload: dict,
) -> dict:
    """Build proposal extras from a request payload."""
    extras: dict = {}
    if handler.manager.extras_config is not None:
        extras = handler.manager.extras_config.proposal_extras_from_dict(payload)
    return extras


def parse_proposal_request(
    handler: Handler,
    payload: dict,
) -> tuple[dict, list[str] | None]:
    """Extract proposal extras and related scenario IDs from a payload."""
    extras = build_proposal_extras(handler, payload)
    related_scenarios = payload.get("related_scenarios")
    scenario_ids = None
    if related_scenarios is not None:
        scenario_ids = extract_related_scenario_ids(payload)
    return extras, scenario_ids


def proposal_to_api(
    proposal: Proposal,
    related_scenario_ids: list[str] | None = None,
    scenarios: dict[str, Scenario] | None = None,
    handler: Handler | None = None,
) -> dict:
    """Convert a proposal entity to API Proposal dict.

    If *scenarios* (ScenarioManager.scenarios) is provided, related
    scenarios are enriched with name, description, and index_diffs.
    """
    related = []
    for sid in related_scenario_ids or []:
        entry: dict = {"scenario_id": sid}
        if scenarios and sid in scenarios:
            state = scenarios[sid]
            entry["scenario_name"] = state.name
            entry["scenario_description"] = state.description
            if handler is not None:
                entry["index_diffs"] = scenario_index_diffs(handler, state)
            entry.update(state.extras)
        related.append(entry)

    return {
        "proposal_id": proposal.proposal_id,
        "proposal_title": proposal.name,
        "proposal_description": proposal.description,
        "created": proposal.created,
        "updated": proposal.updated,
        "status": proposal.status,
        "related_scenarios": related,
        **proposal.extras,
    }


def problem_to_api(problem) -> dict:
    """Convert a problem entity to the API response shape."""
    return {
        "problem_id": problem.problem_id,
        "problem_name": problem.name,
        "problem_description": problem.description,
        "created": problem.created,
        "updated": problem.updated,
        "editable_indexes": get_problem_editable_indexes(problem.extras),
        **{
            key: value
            for key, value in problem.extras.items()
            if key != EDITABLE_INDEXES_KEY
        },
    }


def get_widgets(handler: Handler, values: dict, language: str = "it") -> dict | None:
    """Get widgets from viewer if available, otherwise None."""
    if handler.viewer is not None:
        return handler.viewer.get_widgets(values, language=language)
    return None


def prepare_values(handler: Handler, values: dict) -> dict:
    """Prepare values for evaluation using the viewer if available."""
    if handler.prepare_values_fn is not None:
        return handler.prepare_values_fn(values)
    return values


def arrange_data(handler: Handler, data: typing.Any) -> dict:
    """Convert model output to API dict using arrange_data_fn if available."""
    if handler.arrange_data_fn is not None:
        return handler.arrange_data_fn(data)
    return data


BASE_ROUTE = "/api/v1"
