# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from overtourism.backend.utils.executor_utils import call_executor, list_models
from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.utils.exception import EntityDoesNotExist

logger = logging.getLogger(__name__)


def _create_evaluation(
    manager: Manager,
    territory: str,
    scenario_id: str,
    param_overrides: dict[str, Any] | None = None,
) -> None:
    evaluation = manager.create_evaluation(scenario_id)
    try:
        result = call_executor(territory, param_overrides)
    except Exception:
        logger.exception("Initial evaluation failed for scenario %s", scenario_id)
        manager.fail_evaluation(evaluation)
    else:
        manager.complete_evaluation(evaluation, result)


def bootstrap_entities(manager: Manager) -> None:
    """Create missing base entities and configured scenarios, including their links."""
    config_path = Path(__file__).with_name("bootstrap_config.json")
    with config_path.open(encoding="utf-8") as config_file:
        bootstrap_config_json: list[dict[str, Any]] = json.load(config_file)

    for model in list_models():
        model_config = next(
            (
                config
                for config in bootstrap_config_json
                if config.get("territory") == model["key"]
            ),
            None,
        )
        extra_scenarios: list[dict[str, Any]] = []
        if model_config is not None:
            model_config = dict(model_config)
            extra_scenarios = model_config.pop("scenarios", [])
        names_cfg = (
            BootstrapConfig(**model_config)
            if model_config is not None
            else BootstrapConfig(model["key"])
        )

        try:
            manager.problem_manager.read_problem(names_cfg.problem_id)
        except EntityDoesNotExist:
            manager.problem_manager.create_problem(
                problem_id=names_cfg.problem_id,
                territory=names_cfg.territory,
                name=names_cfg.problem_name,
                description=names_cfg.problem_description,
                extras=names_cfg.problem_extras,
            )

        try:
            manager.scenario_manager.read_scenario(names_cfg.scenario_id)
        except EntityDoesNotExist:
            manager.scenario_manager.create_scenario(
                scenario_id=names_cfg.scenario_id,
                territory=names_cfg.territory,
                name=names_cfg.scenario_name,
                description=names_cfg.scenario_description,
                summary=names_cfg.scenario_summary,
                extras=names_cfg.scenario_extras,
            )
            _create_evaluation(manager, names_cfg.territory, names_cfg.scenario_id)

        try:
            manager.proposal_manager.read_proposal(names_cfg.proposal_id)
        except EntityDoesNotExist:
            manager.proposal_manager.create_proposal(
                proposal_id=names_cfg.proposal_id,
                problem_id=names_cfg.problem_id,
                name=names_cfg.proposal_name,
                description=names_cfg.proposal_description,
                status=names_cfg.proposal_status,
                extras=names_cfg.proposal_extras,
            )

        required_scenario_ids = {names_cfg.scenario_id}
        for scenario_config in extra_scenarios:
            scenario_id = f"{names_cfg.territory}_{scenario_config['key']}"
            required_scenario_ids.add(scenario_id)
            try:
                manager.scenario_manager.read_scenario(scenario_id)
            except EntityDoesNotExist:
                manager.scenario_manager.create_scenario(
                    scenario_id=scenario_id,
                    territory=names_cfg.territory,
                    param_overrides=scenario_config["param_overrides"],
                    name=scenario_config["name"],
                    description=scenario_config["description"],
                )
                _create_evaluation(
                    manager,
                    names_cfg.territory,
                    scenario_id,
                    scenario_config["param_overrides"],
                )

        related_scenario_ids = set(
            manager.relationship_manager.get_related_scenario_ids(names_cfg.proposal_id)
        )
        if not required_scenario_ids.issubset(related_scenario_ids):
            manager.relationship_manager.set_related_scenario_ids(
                proposal_id=names_cfg.proposal_id,
                scenario_ids=sorted(related_scenario_ids | required_scenario_ids),
            )


def main() -> None:
    if os.getenv("DT_OVERTURISM_STANDALONE_MODE", "true").lower() != "true":
        from overtourism.overtourism.backend_extension.api.utils.platform import (
            download_index_data,
        )

        download_index_data()

    from overtourism.overtourism.setup import crud_manager

    bootstrap_entities(crud_manager)


if __name__ == "__main__":
    main()
