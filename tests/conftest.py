# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault(
    "OVERTOURISM_MOLVENO_DATABASE_URL",
    f"sqlite:///{Path(tempfile.gettempdir()) / f'overtourism-molveno-tests-{os.getpid()}.sqlite'}",
)

from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
    EvaluationState,
)
from overtourism.dt_manager.indexes.index import IndexEntry, IndexType
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.sql.store import SQLStore

TIMESTAMP = "2025-01-01T00:00:00Z"
TENANT = "tenant-alpha"


def _make_problem_payload(
    problem_id: str, *, name: str, description: str
) -> dict[str, Any]:
    return Problem.create_default(
        problem_id,
        TENANT,
        name=name,
        description=description,
        created=TIMESTAMP,
        updated=TIMESTAMP,
        extras={"region": "tn"},
    ).to_dict()


def _make_scenario_payload(
    scenario_id: str,
    *,
    tenant: str,
    index_name: str,
    index_value: dict[str, Any] | float,
    index_type: str,
) -> dict[str, Any]:
    return Scenario.create_default(
        scenario_id,
        tenant,
        name=f"{scenario_id} name",
        description=f"{scenario_id} description",
        created=TIMESTAMP,
        updated=TIMESTAMP,
        extras={"kind": "scenario"},
        index_values=[
            IndexEntry(
                index_name=index_name,
                index_value=index_value,
                index_type=index_type,
            )
        ],
    ).to_dict()


def _make_proposal_payload(
    proposal_id: str,
    *,
    problem_id: str,
    status: str,
) -> dict[str, Any]:
    return Proposal.create_default(
        proposal_id,
        problem_id=problem_id,
        name=f"{proposal_id} name",
        description=f"{proposal_id} description",
        status=status,
        created=TIMESTAMP,
        updated=TIMESTAMP,
        extras={"kind": "proposal"},
    ).to_dict()


def _make_evaluation_payload(
    evaluation_id: str,
    *,
    scenario_id: str,
    state: EvaluationState,
    result: dict[str, Any],
) -> dict[str, Any]:
    return Evaluation.create_default(
        evaluation_id,
        scenario_id=scenario_id,
        type=DEFAULT_EVALUATION_TYPE,
        state=state,
        started=TIMESTAMP,
        finished=TIMESTAMP,
        result=result,
    ).to_dict()


@pytest.fixture
def problem_payload() -> dict[str, Any]:
    return _make_problem_payload(
        "problem-alpha",
        name="Problem Alpha",
        description="Primary problem",
    )


@pytest.fixture
def other_problem_payload() -> dict[str, Any]:
    return _make_problem_payload(
        "problem-beta",
        name="Problem Beta",
        description="Secondary problem",
    )


@pytest.fixture
def scenario_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_scenario_payload(
        "scenario-alpha",
        tenant=problem_payload["tenant"],
        index_name="visits",
        index_value={"mean": 12.5},
        index_type=IndexType.CONSTANT.value,
    )


@pytest.fixture
def other_scenario_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_scenario_payload(
        "scenario-beta",
        tenant=problem_payload["tenant"],
        index_name="crowding",
        index_value=3.0,
        index_type=IndexType.UNIFORM.value,
    )


@pytest.fixture
def proposal_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_proposal_payload(
        "proposal-alpha",
        problem_id=problem_payload["problem_id"],
        status="draft",
    )


@pytest.fixture
def other_proposal_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_proposal_payload(
        "proposal-beta",
        problem_id=problem_payload["problem_id"],
        status="accepted",
    )


@pytest.fixture
def evaluation_payload(scenario_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_evaluation_payload(
        "evaluation-alpha",
        scenario_id=scenario_payload["scenario_id"],
        state=EvaluationState.COMPLETED,
        result={"score": 0.91, "notes": ["ok"]},
    )


@pytest.fixture
def other_evaluation_payload(other_scenario_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_evaluation_payload(
        "evaluation-beta",
        scenario_id=other_scenario_payload["scenario_id"],
        state=EvaluationState.FAILED,
        result={"score": 0.12, "notes": ["retry"]},
    )


@pytest.fixture
def sql_store(tmp_path) -> SQLStore:
    return SQLStore(f"sqlite:///{tmp_path / 'store.db'}")
