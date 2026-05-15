# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest
from overtourism.dt_manager.stores.enums import ProblemDocumentKey
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
    ScenarioDoesNotExist,
)


def _normalize_problem_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key.value if isinstance(key, ProblemDocumentKey) else key: value
        for key, value in document.items()
    }


def _identity_problem_document(document: dict[str, Any]) -> dict[str, Any]:
    return document


@dataclass(frozen=True)
class StoreCase:
    fixture_name: str
    problem_document_loader: Callable[[dict[str, Any]], dict[str, Any]]
    missing_checks: tuple[tuple[str, str, type[BaseException]], ...]


LOCAL_CASE = StoreCase(
    fixture_name="local_store",
    problem_document_loader=_normalize_problem_document,
    missing_checks=(
        ("load_scenario", "missing-scenario", ScenarioDoesNotExist),
        ("load_evaluation", "missing-evaluation", EvaluationDoesNotExist),
    ),
)

SQL_CASE = StoreCase(
    fixture_name="sql_store",
    problem_document_loader=_identity_problem_document,
    missing_checks=(
        ("load_scenario", "missing-scenario", ScenarioDoesNotExist),
        ("delete_scenario", "missing-scenario", ScenarioDoesNotExist),
        ("delete_proposal", "missing-proposal", ProposalDoesNotExist),
        ("load_evaluation", "missing-evaluation", EvaluationDoesNotExist),
        ("delete_evaluation", "missing-evaluation", EvaluationDoesNotExist),
    ),
)


STORE_CASES = [
    pytest.param(LOCAL_CASE, id="local"),
    pytest.param(SQL_CASE, id="sql"),
]


def _get_store(request: pytest.FixtureRequest, case: StoreCase) -> Any:
    return request.getfixturevalue(case.fixture_name)


@pytest.mark.parametrize("case", STORE_CASES)
def test_problem_document_round_trip_and_delete_problem(
    request: pytest.FixtureRequest,
    case: StoreCase,
    problem_payload,
    other_problem_payload,
    problem_document,
) -> None:
    store = _get_store(request, case)
    problem_id = problem_payload["problem_id"]
    other_problem_id = other_problem_payload["problem_id"]

    store.save_problem_document(problem_id, problem_document)
    store.save_problem(other_problem_id, other_problem_payload)

    assert store.list_problems() == [problem_id, other_problem_id]
    assert (
        case.problem_document_loader(store.load_problem_document(problem_id))
        == problem_document
    )
    assert store.load_problem(problem_id) == problem_payload
    assert store.load_problem(other_problem_id) == other_problem_payload

    store.delete_problem(problem_id)

    assert store.list_problems() == [other_problem_id]
    assert store.load_scenarios(problem_id) == []
    assert store.load_proposals(problem_id) == []
    assert store.load_evaluations(problem_id) == []

    with pytest.raises(FileNotFoundError):
        store.load_problem_document(problem_id)


@pytest.mark.parametrize("case", STORE_CASES)
def test_entity_round_trip_and_sorted_listings(
    request: pytest.FixtureRequest,
    case: StoreCase,
    problem_payload,
    scenario_payload,
    other_scenario_payload,
    proposal_payload,
    other_proposal_payload,
    evaluation_payload,
    other_evaluation_payload,
) -> None:
    store = _get_store(request, case)
    problem_id = problem_payload["problem_id"]

    store.save_problem(problem_id, problem_payload)
    store.save_scenario(
        problem_id,
        other_scenario_payload["scenario_id"],
        other_scenario_payload,
    )
    store.save_scenario(problem_id, scenario_payload["scenario_id"], scenario_payload)

    store.save_proposal(
        problem_id,
        other_proposal_payload["proposal_id"],
        other_proposal_payload,
    )
    store.save_proposal(problem_id, proposal_payload["proposal_id"], proposal_payload)

    store.save_evaluation(
        problem_id,
        other_evaluation_payload["evaluation_id"],
        other_evaluation_payload,
    )
    store.save_evaluation(
        problem_id,
        evaluation_payload["evaluation_id"],
        evaluation_payload,
    )

    assert [item["scenario_id"] for item in store.load_scenarios(problem_id)] == [
        scenario_payload["scenario_id"],
        other_scenario_payload["scenario_id"],
    ]
    assert (
        store.load_scenario(problem_id, scenario_payload["scenario_id"])
        == scenario_payload
    )

    assert [item["proposal_id"] for item in store.load_proposals(problem_id)] == [
        proposal_payload["proposal_id"],
        other_proposal_payload["proposal_id"],
    ]

    assert [item["evaluation_id"] for item in store.load_evaluations(problem_id)] == [
        evaluation_payload["evaluation_id"],
        other_evaluation_payload["evaluation_id"],
    ]
    assert (
        store.load_evaluation(problem_id, evaluation_payload["evaluation_id"])
        == evaluation_payload
    )

    store.delete_evaluation(problem_id, other_evaluation_payload["evaluation_id"])
    store.delete_scenario(problem_id, other_scenario_payload["scenario_id"])
    store.delete_proposal(problem_id, other_proposal_payload["proposal_id"])

    assert [item["scenario_id"] for item in store.load_scenarios(problem_id)] == [
        scenario_payload["scenario_id"],
    ]
    assert [item["proposal_id"] for item in store.load_proposals(problem_id)] == [
        proposal_payload["proposal_id"],
    ]
    assert [item["evaluation_id"] for item in store.load_evaluations(problem_id)] == [
        evaluation_payload["evaluation_id"],
    ]

    with pytest.raises(ScenarioDoesNotExist):
        store.load_scenario(problem_id, other_scenario_payload["scenario_id"])
    with pytest.raises(EvaluationDoesNotExist):
        store.load_evaluation(problem_id, other_evaluation_payload["evaluation_id"])


@pytest.mark.parametrize(
    ("case", "method_name", "arguments", "expected_message"),
    [
        pytest.param(
            LOCAL_CASE,
            "save_scenario",
            ("scenario-wrong",),
            "Scenario identifiers do not match the provided arguments",
            id="local-save-scenario",
        ),
        pytest.param(
            LOCAL_CASE,
            "save_proposal",
            ("proposal-wrong",),
            "Proposal identifiers do not match the provided arguments",
            id="local-save-proposal",
        ),
        pytest.param(
            LOCAL_CASE,
            "save_evaluation",
            ("evaluation-wrong",),
            "Evaluation identifiers do not match the provided arguments",
            id="local-save-evaluation",
        ),
        pytest.param(
            SQL_CASE,
            "save_scenario",
            ("scenario-wrong",),
            "Scenario identifiers do not match the provided arguments",
            id="sql-save-scenario",
        ),
        pytest.param(
            SQL_CASE,
            "save_proposal",
            ("proposal-wrong",),
            "Proposal identifiers do not match the provided arguments",
            id="sql-save-proposal",
        ),
        pytest.param(
            SQL_CASE,
            "save_evaluation",
            ("evaluation-wrong",),
            "Evaluation identifiers do not match the provided arguments",
            id="sql-save-evaluation",
        ),
    ],
)
def test_identifier_mismatch_raises_value_error(
    request: pytest.FixtureRequest,
    case: StoreCase,
    method_name,
    arguments,
    expected_message,
    problem_payload,
    scenario_payload,
    proposal_payload,
    evaluation_payload,
) -> None:
    store = _get_store(request, case)
    problem_id = problem_payload["problem_id"]
    payloads = {
        "save_scenario": scenario_payload,
        "save_proposal": proposal_payload,
        "save_evaluation": evaluation_payload,
    }

    with pytest.raises(ValueError, match=expected_message):
        getattr(store, method_name)(problem_id, *arguments, payloads[method_name])


@pytest.mark.parametrize("case", STORE_CASES)
def test_missing_entities_raise(
    request: pytest.FixtureRequest, case: StoreCase
) -> None:
    store = _get_store(request, case)

    with pytest.raises(FileNotFoundError):
        store.load_problem("missing-problem")

    for method_name, entity_id, expected_exception in case.missing_checks:
        with pytest.raises(expected_exception):
            getattr(store, method_name)("missing-problem", entity_id)
