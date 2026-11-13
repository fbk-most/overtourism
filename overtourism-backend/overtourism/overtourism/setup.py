# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path

from overtourism.backend.auth.identity.sql_repository import SQLUserRepository
from overtourism.backend.auth.identity.user_manager import UserManager
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.session.config import SessionCleanupConfig
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.metadata import ExtrasConfig

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
    problem_keys=frozenset(("objective", "links")),
    proposal_keys=frozenset(("resources", "context", "impact")),
    scenario_keys=frozenset("index_diffs"),
)
session_cleanup_config = SessionCleanupConfig()

crud_manager = Manager(
    store_conf,
    extras_config,
    session_cleanup_config=session_cleanup_config,
)
sql_store = SQLStore(database_url)
user_repository = SQLUserRepository(sql_store.engine, sql_store.session_factory)

# ──────────────────────────────────────────────
# Handler
# ──────────────────────────────────────────────


def build_handler() -> Handler:
    """Build the molveno backend handler and its collaborators."""
    return Handler(
        manager=crud_manager,
        user_manager=UserManager(user_repository),
    )
