# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.utils.utils import get_timestamp

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.stores.classes.base import Store


class ProblemManager:
    """Manage problem entities directly against the store."""

    def __init__(
        self,
        store: Store,
    ) -> None:
        self.store = store

    # ───────────────────────────────────────────────────────────
    # CRUD
    # ───────────────────────────────────────────────────────────

    def create_problem(
        self,
        problem_id: str,
        tenant: str,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Problem:
        """Create and persist a new problem."""
        problem = Problem.create_default(
            problem_id,
            tenant,
            name=name,
            description=description,
            extras=extras,
        )
        self.store.save_problem(problem.to_dict())
        return problem

    def read_problem(self, problem_id: str) -> Problem:
        """Return a problem loaded from the store.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to return.

        Returns
        -------
        Problem
            Persisted problem instance.
        """
        return Problem.from_dict(self.store.load_problem(problem_id))

    def list_problems(self, tenant: str | None = None) -> list[Problem]:
        """Return all persisted problems."""
        return [
            Problem.from_dict(problem_data)
            for problem_data in self.store.load_problems(tenant=tenant)
        ]

    def update_problem(
        self,
        problem_id: str,
        name: str | None = None,
        description: str | None = None,
        extras: dict | None = None,
    ) -> Problem:
        """Update a persisted problem with new metadata."""
        updated = False
        problem = self.read_problem(problem_id)
        if name is not None:
            problem.name = name
            updated = True
        if description is not None:
            problem.description = description
            updated = True
        if extras is not None:
            for key, value in extras.items():
                problem.extras[key] = value
            updated = True
        if updated:
            problem.version += 1
            problem.updated = get_timestamp()
            self.store.save_problem(problem.to_dict())
        return problem

    def delete_problem(self, problem_id: str) -> None:
        """Remove a problem from storage.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        self.store.delete_problem(problem_id)
