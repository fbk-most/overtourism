# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BaseConfig:
    """Default problem configuration for manager initialization."""

    problem_id: str = "default"
    tenant: str = "default"
    problem_name: str = "Default problem"
    problem_description: str = "Default problem."
    problem_extras: dict = field(default_factory=dict)

    scenario_id: str = "default"
    scenario_name: str = "Default scenario"
    scenario_description: str = "Default scenario."
    scenario_extras: dict = field(default_factory=dict)

    proposal_id: str = "default"
    proposal_name: str = "Default proposal"
    proposal_description: str = "Default proposal"
    proposal_status: str = "accepted"
    proposal_extras: dict = field(default_factory=dict)
