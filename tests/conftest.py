# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from overtourism.backend.api.main import create_app
from overtourism.backend.api.v2.scenario import scenario_router
from overtourism.backend.auth.dependencies import Handler, get_auth_context
from overtourism.backend.auth.models import AuthContext
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
from overtourism.overtourism.backend_extension.api.v2.problem import problem_router
from overtourism.overtourism.backend_extension.api.v2.proposal import proposal_router
from overtourism.overtourism.backend_extension.api.v2.widget import widget_router
from tests.overtourism.test_support import (
    DEFAULT_PROBLEM_ID,
    DEFAULT_PROPOSAL_ID,
    DEFAULT_SCENARIO_ID,
    DEFAULT_TENANT,
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
TENANT = DEFAULT_TENANT


@pytest.fixture
def tenant() -> str:
    return TENANT


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
    param_overrides: dict[str, Any],
) -> dict[str, Any]:
    return Scenario.create_default(
        scenario_id,
        tenant,
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


def _suite_kind(request: pytest.FixtureRequest) -> str:
    path = request.node.path.as_posix()
    if "/tests/overtourism/overtourism/api_v2/" in path:
        return "layer3"
    return "backend"


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
        param_overrides={"visits": 12.5},
    )


@pytest.fixture
def other_scenario_payload(problem_payload: dict[str, Any]) -> dict[str, Any]:
    return _make_scenario_payload(
        "scenario-beta",
        tenant=problem_payload["tenant"],
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
            problem_keys=frozenset({"objective", "groups", "links"}),
        ),
    )
    bootstrap_default_entities(manager, TENANT)
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
        TENANT: FakeExecutionService(fake_model, fake_model_evaluator)
    }
    return handler


def _build_app(handler: Handler, suite_kind: str):
    if suite_kind == "layer3":
        return create_app(
            handler,
            include_problem_router=False,
            include_proposal_router=False,
            include_scenario_router=False,
            extra_routers=[
                problem_router,
                proposal_router,
                scenario_router,
                widget_router,
            ],
        )
    return create_app(handler)


@pytest.fixture
def client(handler: Handler, request: pytest.FixtureRequest):
    app = _build_app(handler, _suite_kind(request))
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=TENANT,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def error_client(handler: Handler, request: pytest.FixtureRequest):
    app = _build_app(handler, _suite_kind(request))
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        authenticated=False,
        tenant=TENANT,
        subject=None,
        token=None,
        claims={},
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
