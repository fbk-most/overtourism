# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, overload

from pydantic import BaseModel

from overtourism.backend.api.models.problem import (
    PostProblemData as BasePostProblemData,
)
from overtourism.backend.api.models.problem import (
    UpdateProblemData as BaseUpdateProblemData,
)
from overtourism.backend.api.models.proposal import (
    PostProposalData as BasePostProposalData,
)
from overtourism.backend.api.models.proposal import (
    UpdateProposalData as BaseUpdateProposalData,
)
from overtourism.backend.handler import Handler
from overtourism.overtourism.backend_extension.api.models.problem import (
    OvertourismProblemData,
)
from overtourism.overtourism.backend_extension.api.models.proposal import (
    OvertourismProposalData,
)

# ──────────────────────────────────────────────
# Conversion functions for overtourism API models
# ──────────────────────────────────────────────


def _model_to_api_overtourism[ModelT: BaseModel](
    data: dict[str, Any],
    model_class: type[ModelT],
) -> ModelT:
    """Convert a backend entity to an overtourism API entity."""
    return model_class(**{**data, **data.pop("extras", {})})


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


@overload
def prepare_problem_payload(
    problem_id: None,
    territory: str,
    payload: dict[str, Any],
    handler: Handler,
) -> BasePostProblemData: ...


@overload
def prepare_problem_payload(
    problem_id: str,
    territory: str,
    payload: dict[str, Any],
    handler: Handler,
) -> BaseUpdateProblemData: ...


def prepare_problem_payload(
    problem_id: str | None,
    territory: str,
    payload: dict[str, Any],
    handler: Handler,
) -> BaseUpdateProblemData | BasePostProblemData:
    extras = payload.pop("extras", None)
    if extras is None:
        extras = {}
        extras["objective"] = payload.pop("objective", None)
        extras["links"] = payload.pop("links", None)

    extras = handler.manager.problem_extras_from_dict(extras)

    payload["extras"] = extras
    payload["territory"] = territory

    if problem_id is not None:
        payload["problem_id"] = problem_id
        return BaseUpdateProblemData(**payload)

    return BasePostProblemData(**payload)


def to_problem_api_overtourism(data: dict[str, Any]) -> OvertourismProblemData:
    """Convert a backend problem entity to an overtourism API problem entity."""
    return _model_to_api_overtourism(data, OvertourismProblemData)


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


@overload
def prepare_proposal_payload(
    proposal_id: None,
    payload: dict[str, Any],
    handler: Handler,
) -> BasePostProposalData: ...


@overload
def prepare_proposal_payload(
    proposal_id: str,
    payload: dict[str, Any],
    handler: Handler,
) -> BaseUpdateProposalData: ...


def prepare_proposal_payload(
    proposal_id: str | None,
    payload: dict[str, Any],
    handler: Handler,
) -> BasePostProposalData | BaseUpdateProposalData:
    extras = payload.pop("extras", None)
    if extras is None:
        extras = {}
        extras["related_scenario_ids"] = payload.pop("related_scenario_ids", None)

    extras = handler.manager.proposal_extras_from_dict(extras)
    payload["extras"] = extras
    if proposal_id is not None:
        payload["proposal_id"] = proposal_id
        return BaseUpdateProposalData(**payload)
    return BasePostProposalData(**payload)


def to_proposal_api_overtourism(data: dict[str, Any]) -> OvertourismProposalData:
    """Convert a backend proposal entity to an overtourism API proposal entity."""
    return _model_to_api_overtourism(data, OvertourismProposalData)
