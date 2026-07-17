# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from overtourism.dt_manager.proposal.proposal import ProposalStatus


class ProposalData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    proposal_id: str
    problem_id: str
    version: int = 0
    name: str | None = None
    description: str | None = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created: str | None = None
    updated: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
    related_scenario_ids: list[str] = Field(default_factory=list)


class PostProposalData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    problem_id: str
    name: str | None = None
    description: str | None = None
    status: ProposalStatus | None = None
    extras: dict[str, Any] | None = None
    related_scenario_ids: list[str] | None = None


class UpdateProposalData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    version: int | None = None
    name: str | None = None
    description: str | None = None
    status: ProposalStatus | None = None
    extras: dict[str, Any] | None = None
    related_scenario_ids: list[str] | None = None
