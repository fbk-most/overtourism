# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from types import ModuleType

import requests
from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.overtourism import bootstrap


def _create_manager(tmp_path, database_name: str) -> Manager:
    return Manager(
        StoreConfig(
            "sql",
            {"url": f"sqlite:///{tmp_path / database_name}"},
        )
    )


def test_bootstrap_initializes_models_and_is_idempotent(
    tmp_path,
    monkeypatch,
) -> None:
    manager = _create_manager(tmp_path, "bootstrap.db")
    manager.problem_manager.create_problem(
        "fazzon_base_problem",
        "fazzon",
        name="Fazzon",
    )
    manager.scenario_manager.create_scenario(
        "fazzon_base_scenario",
        "fazzon",
        name="Base scenario",
    )
    manager.proposal_manager.create_proposal(
        "fazzon_base_proposal",
        "fazzon_base_problem",
        name="Fazzon proposal",
        status="draft",
    )
    manager.scenario_manager.create_scenario(
        "fazzon_a1_no_cap",
        "fazzon",
        name="A1 without cap",
    )

    monkeypatch.setattr(bootstrap, "list_models", lambda: [{"key": "fazzon"}])
    evaluations: list[tuple[str, dict | None]] = []

    def evaluate_model(territory: str, param_overrides: dict | None = None) -> dict:
        evaluations.append((territory, param_overrides))
        return {}

    monkeypatch.setattr(bootstrap, "call_executor", evaluate_model)

    try:
        bootstrap.bootstrap_entities(manager)

        expected_scenario_ids = {
            "fazzon_base_scenario",
            "fazzon_a1_no_cap",
            "fazzon_a2_reduced_cap",
            "fazzon_b1_shuttle_only",
            "fazzon_b2_price_10",
            "fazzon_c1_piano_2026",
            "fazzon_c2_strong",
        }
        assert {
            scenario.scenario_id
            for scenario in manager.list_scenarios(territory="fazzon")
        } == expected_scenario_ids
        assert (
            set(
                manager.relationship_manager.get_related_scenario_ids(
                    "fazzon_base_proposal"
                )
            )
            == expected_scenario_ids
        )
        new_scenario_ids = expected_scenario_ids - {
            "fazzon_base_scenario",
            "fazzon_a1_no_cap",
        }
        assert len(manager.list_evaluations(territory="fazzon")) == len(
            new_scenario_ids
        )
        assert len(evaluations) == len(new_scenario_ids)

        bootstrap.bootstrap_entities(manager)

        assert len(manager.list_evaluations(territory="fazzon")) == len(evaluations)
        assert len(evaluations) == len(new_scenario_ids)
    finally:
        manager.store.engine.dispose()


def test_main_downloads_platform_data_and_records_failed_evaluation(
    tmp_path,
    monkeypatch,
) -> None:
    manager = _create_manager(tmp_path, "platform-bootstrap.db")
    downloaded: list[bool] = []
    monkeypatch.setenv("DT_OVERTURISM_STANDALONE_MODE", "false")
    monkeypatch.setattr(
        "overtourism.overtourism.backend_extension.api.utils.platform.download_index_data",
        lambda: downloaded.append(True),
    )
    monkeypatch.setattr(bootstrap, "list_models", lambda: [{"key": "custom"}])
    setup_module = ModuleType("overtourism.overtourism.setup")
    setup_module.crud_manager = manager
    monkeypatch.setitem(sys.modules, setup_module.__name__, setup_module)

    def model_unavailable(*_args, **_kwargs):
        raise requests.ConnectionError("Model API unavailable")

    monkeypatch.setattr(bootstrap, "call_executor", model_unavailable)

    try:
        bootstrap.main()

        assert downloaded == [True]
        assert manager.problem_manager.read_problem("custom_base_problem")
        assert manager.proposal_manager.read_proposal("custom_base_proposal")
        assert manager.relationship_manager.get_related_scenario_ids(
            "custom_base_proposal"
        ) == ["custom_base_scenario"]
        evaluations = manager.list_evaluations(territory="custom")
        assert len(evaluations) == 1
        assert evaluations[0].state is EvaluationState.FAILED
    finally:
        manager.store.engine.dispose()
