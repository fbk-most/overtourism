# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.manager.config import BootstrapConfig


def test_base_problem_config_defaults() -> None:
    config = BootstrapConfig()

    assert config.problem_id == "default_base_problem"
    assert config.territory == "default"
    assert config.problem_name == "Sandbox problem"
    assert config.problem_description == "Sandbox problem."
    assert config.problem_extras == {}
    assert config.scenario_id == "default_base_scenario"
    assert config.scenario_name == "Base scenario"
    assert config.scenario_description == "Base scenario."
    assert config.scenario_extras == {}
    assert config.proposal_id == "default_base_proposal"
    assert config.proposal_name == "Sandbox proposal"
    assert config.proposal_description == "Sandbox proposal."
    assert config.proposal_status == "draft"
    assert config.proposal_extras == {}


def test_base_problem_config_accepts_custom_values() -> None:
    config = BootstrapConfig(
        territory="territory-alpha",
        problem_name="Problem Alpha",
        problem_description="Primary problem",
        problem_extras={"region": "tn"},
        scenario_name="Scenario Alpha",
        scenario_description="Primary scenario",
        scenario_extras={"kind": "scenario"},
        proposal_name="Proposal Alpha",
        proposal_description="Primary proposal",
        proposal_status="draft",
        proposal_extras={"priority": "high"},
    )

    assert config.problem_id == "territory-alpha_base_problem"
    assert config.territory == "territory-alpha"
    assert config.problem_name == "Problem Alpha"
    assert config.problem_description == "Primary problem"
    assert config.problem_extras == {"region": "tn"}
    assert config.scenario_id == "territory-alpha_base_scenario"
    assert config.scenario_name == "Scenario Alpha"
    assert config.scenario_description == "Primary scenario"
    assert config.scenario_extras == {"kind": "scenario"}
    assert config.proposal_id == "territory-alpha_base_proposal"
    assert config.proposal_name == "Proposal Alpha"
    assert config.proposal_description == "Primary proposal"
    assert config.proposal_status == "draft"
    assert config.proposal_extras == {"priority": "high"}
