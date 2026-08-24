# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BootstrapConfig:
    """Default problem configuration for manager initialization."""

    tenant: str = "default"

    problem_id: str = field(init=False)
    problem_name: str = "Sandbox problem"
    problem_description: str = "Sandbox problem."
    problem_extras: dict = field(default_factory=dict)

    scenario_id: str = field(init=False)
    scenario_name: str = "Base scenario"
    scenario_description: str = "Base scenario."
    scenario_extras: dict = field(default_factory=dict)

    proposal_id: str = field(init=False)
    proposal_name: str = "Sandbox proposal"
    proposal_description: str = "Sandbox proposal."
    proposal_status: str = "draft"
    proposal_extras: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.problem_id = f"{self.tenant}_base_problem"
        self.scenario_id = f"{self.tenant}_base_scenario"
        self.proposal_id = f"{self.tenant}_base_proposal"
