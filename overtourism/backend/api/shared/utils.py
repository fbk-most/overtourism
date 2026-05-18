# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from slugify import slugify

from overtourism.backend.api.shared.exceptions import ProblemNotFound
from overtourism.backend.handler import Handler
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.scenario.values import values_as_scipy

if typing.TYPE_CHECKING:
    from overtourism.backend.api.shared.models.problem import (
        PostProblemData,
        UpdateProblemData,
    )
    from overtourism.backend.api.shared.models.problem import Proposal as ProposalModel
    from overtourism.dt_manager.classes.model import ModelOutput


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


def get_problem_or_404(handler: Handler, problem_id: str) -> Problem:
    """Return a problem or raise a not-found error."""
    try:
        return handler.manager.read_problem(problem_id)
    except KeyError:
        raise ProblemNotFound(f"Problem '{problem_id}' not found")


def problem_from_model(
    handler: Handler,
    data: PostProblemData,
) -> dict:
    """Extract problem fields and extras from a payload."""
    return {
        "name": data.problem_name,
        "description": data.problem_description,
        "created": data.created,
        "updated": data.updated,
        "extras": build_problem_extras(handler, data.model_dump(exclude_unset=True)),
    }


def problem_update_from_model(
    handler: Handler,
    data: UpdateProblemData,
) -> dict:
    """Extract problem update fields and extras from a payload."""
    return {
        "name": data.problem_name,
        "description": data.problem_description,
        "updated": data.updated,
        "extras": build_problem_extras(handler, data.model_dump(exclude_unset=True)),
    }


def problem_to_api(problem: Problem) -> dict:
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
            if key != "editable_indexes"
        },
    }


def build_problem_extras(
    handler: Handler,
    payload: dict,
) -> dict:
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
) -> dict:
    """Extract proposal extras and related scenario IDs from a payload."""
    extras = handler.manager.proposal_extras_from_dict(
        data.model_dump(exclude_unset=True)
    )
    return {
        "name": data.proposal_title,
        "description": data.proposal_description,
        "status": data.status or "draft",
        "extras": extras,
        "related_scenario_ids": [
            related_scenario.scenario_id for related_scenario in data.related_scenarios
        ],
    }


def build_related_scenarios(
    handler: Handler,
    problem_id: str,
    proposal_id: str,
) -> list[dict]:
    """Build related_scenarios entries from scenario IDs."""
    scenarios = {
        scenario.scenario_id: scenario
        for scenario in handler.manager.list_scenarios(problem_id)
    }
    related_sids = handler.manager.problem_manager.get_related_scenario_ids(
        problem_id, proposal_id
    )
    related = []
    for sid in related_sids:
        state = scenarios[sid]
        related.append(
            {
                "scenario_id": state.scenario_id,
                "scenario_name": state.name,
                "scenario_description": state.description,
                "index_diffs": scenario_index_diffs(handler, state),
                **state.extras,
            }
        )
    return related


def proposal_to_api(
    handler: Handler,
    problem_id: str,
    proposal: Proposal,
) -> dict:
    """Convert a proposal entity to API Proposal dict."""
    return {
        "proposal_id": proposal.proposal_id,
        "proposal_title": proposal.name,
        "proposal_description": proposal.description,
        "created": proposal.created,
        "updated": proposal.updated,
        "status": proposal.status,
        "related_scenarios": build_related_scenarios(
            handler, problem_id, proposal.proposal_id
        ),
        **proposal.extras,
    }


# ──────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────


def get_widgets(handler: Handler, values: dict, language: str = "it") -> dict | None:
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
# Scenario
# ──────────────────────────────────────────────


def scenario_to_api(handler: Handler, scenario: Scenario) -> dict:
    """Convert a scenario entity to the API response shape."""
    return {
        "problem_id": scenario.problem_id,
        "scenario_id": scenario.scenario_id,
        "scenario_name": scenario.name,
        "scenario_description": scenario.description,
        "created": scenario.created,
        "updated": scenario.updated,
        "index_diffs": scenario_index_diffs(handler, scenario),
        **scenario.extras,
    }


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


def scenario_index_diffs(handler: Handler, scenario: Scenario) -> dict[str, str]:
    """Compute the model index differences for a scenario on demand."""
    return handler.manager.model_evaluator.get_index_diffs(
        handler.manager.model,
        values=values_as_scipy(scenario),
    )


def evaluation_result_to_dict(result: ModelOutput | dict | None) -> dict:
    """Normalize a model output or mapping into a plain dictionary."""
    if result is None:
        return {}
    return result.to_dict() if hasattr(result, "to_dict") else result


def model_values(handler: Handler) -> dict:
    """Return the base model values exposed by the facade manager."""
    return handler.manager.model_evaluator.get_model_values(handler.manager.model)


# ──────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────


def slugify_name(name: str) -> str:
    """Generate a slugified identifier from a name."""
    return slugify(name)
