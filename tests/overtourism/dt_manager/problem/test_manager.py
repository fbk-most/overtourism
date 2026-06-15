# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.problem.manager import ProblemManager
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.dt_manager.utils.exception import EntityDoesNotExist


def _make_manager(tmp_path) -> ProblemManager:
    return ProblemManager(SQLStore(f"sqlite:///{tmp_path / 'store.db'}"))


def test_problem_manager_persists_problem_state_directly_to_store(tmp_path) -> None:
    manager = _make_manager(tmp_path)

    manager.create_problem(
        "problem-alpha",
        tenant="molveno",
        name="Problem Alpha",
        description="Primary problem",
        extras={"region": "tn"},
    )

    problem = manager.read_problem("problem-alpha")
    assert problem.problem_id == "problem-alpha"
    assert problem.tenant == "molveno"
    assert problem.name == "Problem Alpha"
    assert problem.description == "Primary problem"
    assert problem.extras == {"region": "tn"}

    problem.name = "Cached only"
    assert manager.read_problem("problem-alpha").name == "Problem Alpha"

    manager.update_problem(
        "problem-alpha",
        name="Updated problem",
        extras={"theme": "mobility"},
    )
    assert manager.read_problem("problem-alpha").name == "Updated problem"
    assert manager.read_problem("problem-alpha").extras == {
        "region": "tn",
        "theme": "mobility",
    }

    assert [item.problem_id for item in manager.list_problems()] == [
        "problem-alpha",
    ]
    assert [item.problem_id for item in manager.list_problems(tenant="molveno")] == [
        "problem-alpha",
    ]

    manager.delete_problem("problem-alpha")
    assert manager.list_problems() == []

    with pytest.raises(EntityDoesNotExist):
        manager.read_problem("problem-alpha")
