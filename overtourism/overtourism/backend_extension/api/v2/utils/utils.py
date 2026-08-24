# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from typing import Any

from overtourism.backend.api.v2.models.problem import (
    PostProblemData as BasePostProblemData,
)
from overtourism.backend.api.v2.models.problem import (
    UpdateProblemData as BaseUpdateProblemData,
)
from overtourism.backend.api.v2.models.proposal import (
    PostProposalData as BasePostProposalData,
)
from overtourism.backend.api.v2.models.proposal import (
    UpdateProposalData as BaseUpdateProposalData,
)
from overtourism.backend.handler import Handler
from overtourism.overtourism.backend_extension.api.v2.models.problem import (
    OvertourismProblemData,
)
from overtourism.overtourism.backend_extension.api.v2.models.proposal import (
    OvertourismProposalData,
)

if typing.TYPE_CHECKING:
    from pydantic import BaseModel


# ──────────────────────────────────────────────
# Conversion functions for overtourism API models
# ──────────────────────────────────────────────


def _model_to_api_overtourism(data: dict, model_class: BaseModel) -> BaseModel:
    """Convert a backend entity to an overtourism API entity."""
    return model_class(**{**data, **data.pop("extras", {})})


# ──────────────────────────────────────────────
# Problem
# ──────────────────────────────────────────────


def prepare_problem_payload(
    problem_id: str,
    tenant: str,
    payload: dict[str, Any],
    handler: Handler,
) -> BaseUpdateProblemData | BasePostProblemData:
    extras = payload.pop("extras", None)
    if extras is None:
        extras = {}
        extras["objective"] = payload.pop("objective", None)
        extras["groups"] = payload.pop("groups", None)
        extras["links"] = payload.pop("links", None)

    extras = handler.manager.problem_extras_from_dict(extras)

    editable_indexes = extras.get("editable_indexes", [])
    extras["editable_indexes"] = [str(item) for item in editable_indexes]

    payload["extras"] = extras
    payload["tenant"] = tenant

    if problem_id is not None:
        payload["problem_id"] = problem_id
        return BaseUpdateProblemData(**payload)

    return BasePostProblemData(**payload)


def to_problem_api_overtourism(data: BasePostProblemData) -> OvertourismProblemData:
    """Convert a backend problem entity to an overtourism API problem entity."""
    return _model_to_api_overtourism(data, OvertourismProblemData)


# ──────────────────────────────────────────────
# Proposal
# ──────────────────────────────────────────────


def prepare_proposal_payload(
    proposal_id: str,
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


def to_proposal_api_overtourism(data: BasePostProposalData) -> OvertourismProposalData:
    """Convert a backend proposal entity to an overtourism API proposal entity."""
    return _model_to_api_overtourism(data, OvertourismProposalData)
