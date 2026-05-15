# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.classes.metadata import ExtrasConfig


def test_extras_config_filters_configured_keys() -> None:
    config = ExtrasConfig(
        problem_keys=frozenset({"region", "owner"}),
        proposal_keys=frozenset({"status"}),
        scenario_keys=frozenset({"kind", "ignored"}),
    )

    data = {
        "region": "tn",
        "owner": "planning",
        "status": "draft",
        "kind": "scenario",
        "ignored": "present",
        "unrelated": "skip",
    }

    assert config.problem_extras_from_dict(data) == {
        "region": "tn",
        "owner": "planning",
    }
    assert config.proposal_extras_from_dict(data) == {"status": "draft"}
    assert config.scenario_extras_from_dict(data) == {
        "kind": "scenario",
        "ignored": "present",
    }


def test_extras_config_defaults_to_empty_mappings() -> None:
    config = ExtrasConfig()

    assert config.problem_extras_from_dict({"region": "tn"}) == {}
    assert config.proposal_extras_from_dict({"status": "draft"}) == {}
    assert config.scenario_extras_from_dict({"kind": "scenario"}) == {}
