# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from overtourism.overtourism.registry import ExecutionManagerRegistry


def bootstrap_default_graph(
    crud_manager, execution_registry: ExecutionManagerRegistry
) -> None:
    """Bootstrap the default problem graph for every registered tenant."""
    for tenant in execution_registry.tenants():
        service = execution_registry.get(tenant)
        names_cfg = crud_manager.name_cfg

        try:
            crud_manager.scenario_manager.read_scenario(names_cfg.scenario_id)
            continue
        except EntityDoesNotExist:
            pass

        crud_manager.problem_manager.create_problem(
            problem_id=names_cfg.problem_id,
            tenant=names_cfg.tenant,
            name=names_cfg.problem_name,
            description=names_cfg.problem_description,
            extras=names_cfg.problem_extras,
        )
        crud_manager.scenario_manager.create_scenario(
            scenario_id=names_cfg.scenario_id,
            tenant=names_cfg.tenant,
            name=names_cfg.scenario_name,
            description=names_cfg.scenario_description,
            extras=names_cfg.scenario_extras,
        )
        evaluation = crud_manager.create_evaluation(names_cfg.scenario_id)
        evaluation = service.execute_evaluation(
            evaluation,
            crud_manager.read_scenario(names_cfg.scenario_id),
        )
        crud_manager.save_evaluation(evaluation)
        crud_manager.proposal_manager.create_proposal(
            proposal_id=names_cfg.proposal_id,
            problem_id=names_cfg.problem_id,
            name=names_cfg.proposal_name,
            description=names_cfg.proposal_description,
            status=names_cfg.proposal_status,
            extras=names_cfg.proposal_extras,
        )
        crud_manager.relationship_manager.link_scenario_proposal(
            proposal_id=names_cfg.proposal_id,
            scenario_id=names_cfg.scenario_id,
        )
