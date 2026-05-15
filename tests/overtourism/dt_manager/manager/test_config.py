# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.config import BaseProblemConfig


def test_base_problem_config_defaults() -> None:
    config = BaseProblemConfig()

    assert config.problem_id == "default"
    assert config.problem_name == "Default problem"
    assert config.problem_description == "Default problem."
    assert config.problem_extras == {}
    assert config.scenario_id == "default"
    assert config.scenario_name == "Default scenario"
    assert config.scenario_description == "Default scenario."
    assert config.scenario_extras == {}
    assert config.proposal_id == "default"
    assert config.proposal_name == "Default proposal"
    assert config.proposal_description == "Default proposal"
    assert config.proposal_status == "accepted"
    assert config.proposal_extras == {}


def test_base_problem_config_accepts_custom_values() -> None:
    config = BaseProblemConfig(
        problem_id="problem-alpha",
        problem_name="Problem Alpha",
        problem_description="Primary problem",
        problem_extras={"region": "tn"},
        scenario_id="scenario-alpha",
        scenario_name="Scenario Alpha",
        scenario_description="Primary scenario",
        scenario_extras={"kind": "scenario"},
        proposal_id="proposal-alpha",
        proposal_name="Proposal Alpha",
        proposal_description="Primary proposal",
        proposal_status="draft",
        proposal_extras={"priority": "high"},
    )

    assert config.problem_id == "problem-alpha"
    assert config.problem_name == "Problem Alpha"
    assert config.problem_description == "Primary problem"
    assert config.problem_extras == {"region": "tn"}
    assert config.scenario_id == "scenario-alpha"
    assert config.scenario_name == "Scenario Alpha"
    assert config.scenario_description == "Primary scenario"
    assert config.scenario_extras == {"kind": "scenario"}
    assert config.proposal_id == "proposal-alpha"
    assert config.proposal_name == "Proposal Alpha"
    assert config.proposal_description == "Primary proposal"
    assert config.proposal_status == "draft"
    assert config.proposal_extras == {"priority": "high"}
