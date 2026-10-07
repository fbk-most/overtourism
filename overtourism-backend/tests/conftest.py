# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from overtourism.backend.auth.tokens.context import AuthContext
from overtourism.backend.auth.tokens.dependencies import get_auth_context
from overtourism.backend.handler import Handler
from overtourism.backend.main import create_app
from overtourism.dt_manager.evaluation.evaluation import (
    DEFAULT_EVALUATION_TYPE,
    Evaluation,
    EvaluationState,
)
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.sql.store import SQLStore
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.stores.enums import StoreType
from overtourism.dt_manager.utils.metadata import ExtrasConfig

from tests.overtourism.test_support import (
    DEFAULT_PROBLEM_ID,
    DEFAULT_PROPOSAL_ID,
    DEFAULT_SCENARIO_ID,
    DEFAULT_TERRITORY,
    FakeExecutionService,
    FakeModelEvaluator,
    RecordingViewer,
    bootstrap_default_entities,
)

os.environ.setdefault(
    "OVERTOURISM_MOLVENO_DATABASE_URL",
    f"sqlite:///{Path(tempfile.gettempdir()) / f'overtourism-molveno-tests-{os.getpid()}.sqlite'}",
)

TIMESTAMP = "2025-01-01T00:00:00Z"
TERRITORY = DEFAULT_TERRITORY


@pytest.fixture
def territory() -> str:
    return TERRITORY


def _make_problem_payload(
    problem_id: str, *, name: str, description: str
) -> dict[str, Any]:
    return Problem.create_default(
        problem_id,
        TERRITORY,
        name=name,
        description=description,
        created=TIMESTAMP,
        updated=TIMESTAMP,
        extras={"region": "tn"},
    ).to_dict()


def _make_scenario_payload(
    scenario_id: str,
    *,
    territory: str,
    param_overrides: dict[str, Any],
) -> dict[str, Any]:
    return Scenario.create_default(
        scenario_id,
        territory,
        name=f"{scenario_id} name",
        description=f"{scenario_id} description",
        created=TIMESTAMP,
        updated=TIMESTAMP,
        extras={"kind": "scenario"},
        param_overrides=param_overrides,
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
        territory=problem_payload["territory"],
        param_overrides={"visits": 12.5},
    )


@pytest.fixture
def other_scenario_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_scenario_payload(
        "scenario-beta",
        territory=problem_payload["territory"],
        param_overrides={"crowding": 3.0},
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


@pytest.fixture
def fake_model() -> Any:
    return SimpleNamespace(name="fake-model", indexes=[])


@pytest.fixture
def fake_model_evaluator(fake_model: Any) -> FakeModelEvaluator:
    return FakeModelEvaluator(fake_model)


@pytest.fixture
def viewer() -> RecordingViewer:
    return RecordingViewer()


@pytest.fixture
def manager(tmp_path) -> Manager:
    manager = Manager(
        store_config=StoreConfig(
            store_type=StoreType.SQL.value,
            config={"url": f"sqlite:///{tmp_path / 'store.db'}"},
        ),
        extras_config=ExtrasConfig(
            problem_keys=frozenset({"objective", "links"}),
        ),
    )
    bootstrap_default_entities(manager, TERRITORY)
    return manager


@pytest.fixture
def problem_id() -> str:
    return DEFAULT_PROBLEM_ID


@pytest.fixture
def scenario_id() -> str:
    return DEFAULT_SCENARIO_ID


@pytest.fixture
def proposal_id() -> str:
    return DEFAULT_PROPOSAL_ID


@pytest.fixture
def handler(
    manager: Manager,
    fake_model: Any,
    fake_model_evaluator: FakeModelEvaluator,
) -> Handler:
    handler = Handler(manager=manager)
    handler.execution_manager_registry = {
        TERRITORY: FakeExecutionService(fake_model, fake_model_evaluator)
    }
    return handler


@pytest.fixture
def client(handler: Handler):
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        territory=TERRITORY,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def error_client(handler: Handler):
    app = create_app(handler)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        territory=TERRITORY,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
