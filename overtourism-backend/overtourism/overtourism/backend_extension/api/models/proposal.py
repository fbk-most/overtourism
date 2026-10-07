# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import Field

from overtourism.backend.api.models.proposal import (
    PostProposalData,
    ProposalData,
    UpdateProposalData,
)


class OvertourismProposalData(ProposalData):
    resources: list[str] = Field(default_factory=list)
    context: str | None = None
    impact: str | None = None
    related_scenario_ids: list[str] = Field(default_factory=list)


class OvertourismPostProposalData(PostProposalData):
    resources: list[str] | None = None
    context: str | None = None
    impact: str | None = None
    related_scenario_ids: list[str] | None = None


class OvertourismUpdateProposalData(UpdateProposalData):
    resources: list[str] | None = None
    context: str | None = None
    impact: str | None = None
    related_scenario_ids: list[str] | None = None
