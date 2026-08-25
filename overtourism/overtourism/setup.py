# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path

from overtourism.backend.api.utils.executor_utils import (
    call_executor,
    call_schema,
    list_models,
)
from overtourism.backend.auth.dependencies import Handler
from overtourism.dt_manager.manager.config import BootstrapConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.exception import EntityDoesNotExist
from overtourism.dt_manager.utils.metadata import ExtrasConfig
from overtourism.overtourism.platform import download_index_data_v2

# ──────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────

# Whether execute standalone, with data already prepared
standalone_mode = os.getenv("DT_OVERTURISM_STANDALONE_MODE", "true").lower() == "true"

if not standalone_mode:
    # download_index_data()
    download_index_data_v2()

# ──────────────────────────────────────────────
# Store
# ──────────────────────────────────────────────

data_dir = Path(__file__).parent / "database"
index_data_path = data_dir / "index_data"
database_url = os.getenv(
    "OVERTOURISM_DATABASE", f"sqlite:///{data_dir / 'overtourism.sqlite'}"
)
store_conf = StoreConfig("sql", {"url": database_url})

# ──────────────────────────────────────────────
# Manager
# ──────────────────────────────────────────────

extras_config = ExtrasConfig(
    problem_keys=frozenset(("objective", "links", "groups", "editable_indexes")),
    proposal_keys=frozenset(("resources", "context", "impact")),
    scenario_keys=frozenset("index_diffs"),
)

crud_manager = Manager(store_conf, extras_config)

# ──────────────────────────────────────────────
# Bootstrap entites
# ──────────────────────────────────────────────

for model in list_models():
    names_cfg = BootstrapConfig(model["key"])

    try:
        crud_manager.scenario_manager.read_scenario(names_cfg.scenario_id)
        continue
    except EntityDoesNotExist:
        pass

    # Call schema
    schema = call_schema(names_cfg.tenant)
    editable_indexes = []
    groups = []
    for i in schema:
        editable_indexes.append(i["name"])
        groups.append(i["category"])
    problem_extras = {
        "editable_indexes": set(editable_indexes),
        "groups": set(groups),
    }

    crud_manager.problem_manager.create_problem(
        problem_id=names_cfg.problem_id,
        tenant=names_cfg.tenant,
        name=names_cfg.problem_name,
        description=names_cfg.problem_description,
        extras=problem_extras,
    )
    crud_manager.scenario_manager.create_scenario(
        scenario_id=names_cfg.scenario_id,
        tenant=names_cfg.tenant,
        name=names_cfg.scenario_name,
        description=names_cfg.scenario_description,
        extras=names_cfg.scenario_extras,
    )
    evaluation = crud_manager.create_evaluation(names_cfg.scenario_id)
    result = call_executor(names_cfg.tenant)
    evaluation.result = result
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


# ──────────────────────────────────────────────
# Handler
# ──────────────────────────────────────────────


def build_handler() -> Handler:
    """Build the molveno backend handler and its collaborators."""
    return Handler(manager=crud_manager)
