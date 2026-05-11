# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.classes.local.io import (
    get_glob,
    load_json,
    save_json,
)
from overtourism.dt_manager.stores.enums import ProblemDocumentKey, ProblemNestedKey
from overtourism.dt_manager.utils.exception import ScenarioDoesNotExist


class LocalIOStore(Store):
    """Local filesystem implementation of the Store interface."""

    def __init__(self, folder: str) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def save_problem(self, problem_id: str, problem_data: dict) -> None:
        path = self.folder / f"{problem_id}.json"
        save_json(self._normalize_problem_document(problem_data), path)

    def load_problem_document(self, problem_id: str) -> dict:
        return self._normalize_problem_document(
            self._load_problem_document(problem_id),
        )

    def save_problem_document(self, problem_id: str, problem_data: dict) -> None:
        self._save_problem_document(problem_id, problem_data)

    def load_problem(self, problem_id: str) -> Problem:
        data = self.load_problem_document(problem_id)
        return Problem.from_dict(data.get("problem", data))

    def _load_problem_document(self, problem_id: str) -> dict:
        path = self._resolve_problem_path(problem_id)
        return load_json(path)

    def _resolve_problem_path(self, problem_id: str) -> Path:
        problem_path = Path(problem_id)
        if problem_path.suffix == ".json":
            return self.folder / problem_path.name
        return (
            self.folder
            / f"{problem_path.stem if problem_path.suffix else problem_id}.json"
        )

    def _save_problem_document(self, problem_id: str, problem_data: dict) -> None:
        self.save_problem(problem_id, problem_data)

    def _normalize_problem_document(self, problem_data: dict) -> dict:
        """Normalize a problem payload to the standard document envelope."""
        if ProblemDocumentKey.PROBLEM in problem_data:
            return {
                ProblemDocumentKey.PROBLEM: problem_data[ProblemDocumentKey.PROBLEM],
                ProblemDocumentKey.SCENARIOS: problem_data.get(
                    ProblemDocumentKey.SCENARIOS,
                    [],
                ),
                ProblemDocumentKey.PROPOSALS: problem_data.get(
                    ProblemDocumentKey.PROPOSALS,
                    [],
                ),
                ProblemDocumentKey.EVALUATIONS: problem_data.get(
                    ProblemDocumentKey.EVALUATIONS,
                    [],
                ),
                ProblemDocumentKey.RELATIONSHIP: problem_data.get(
                    ProblemDocumentKey.RELATIONSHIP,
                    [],
                ),
            }
        return {
            ProblemDocumentKey.PROBLEM: problem_data,
            ProblemDocumentKey.SCENARIOS: [],
            ProblemDocumentKey.PROPOSALS: [],
            ProblemDocumentKey.EVALUATIONS: [],
            ProblemDocumentKey.RELATIONSHIP: [],
        }

    def _load_section_items(
        self,
        problem_id: str,
        section: str,
        factory,
    ):
        problem = self._load_problem_document(problem_id)
        return [factory(item) for item in problem.get(section, [])]

    def _save_section_items(
        self,
        problem_id: str,
        section: str,
        identifier_key: str,
        identifier: str,
        item,
    ) -> None:
        problem = self._load_problem_document(problem_id)
        section_items = self._filter_section_items(
            problem,
            section,
            identifier_key,
            identifier,
        )
        section_items.append(item.to_dict())
        problem[section] = section_items
        self._save_problem_document(problem_id, problem)

    def _delete_section_item(
        self,
        problem_id: str,
        section: str,
        identifier_key: str,
        identifier: str,
    ) -> None:
        problem = self._load_problem_document(problem_id)
        problem[section] = self._filter_section_items(
            problem,
            section,
            identifier_key,
            identifier,
        )
        self._save_problem_document(problem_id, problem)

    def _filter_section_items(
        self,
        problem: dict,
        section: str,
        identifier_key: str,
        identifier: str,
    ) -> list[dict]:
        return [
            existing
            for existing in problem.get(section, [])
            if existing.get(identifier_key) != identifier
        ]

    def list_problems(self) -> list[str]:
        return [
            Path(problem_path).stem
            for problem_path in get_glob(self.folder)
            if Path(problem_path).suffix == ".json"
        ]

    def delete_problem(self, problem_id: str) -> None:
        path = self.folder / f"{problem_id}.json"
        if path.exists():
            path.unlink()

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def save_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        scenario_data: Scenario,
    ) -> None:
        self._save_section_items(
            problem_id,
            ProblemDocumentKey.SCENARIOS,
            ProblemNestedKey.SCENARIO_ID,
            scenario_id,
            scenario_data,
        )

    def load_scenarios(self, problem_id: str) -> list[Scenario]:
        return self._load_section_items(
            problem_id,
            ProblemDocumentKey.SCENARIOS,
            lambda item: Scenario.from_dict(item),
        )

    def load_scenario(self, problem_id: str, scenario_id: str) -> Scenario:
        problem = self._load_problem_document(problem_id)
        try:
            scenario_raw = next(
                s
                for s in problem.get(ProblemDocumentKey.SCENARIOS, [])
                if s.get(ProblemNestedKey.SCENARIO_ID) == scenario_id
            )
        except StopIteration as exc:
            raise ScenarioDoesNotExist(
                f"Scenario with ID {scenario_id} does not exist"
            ) from exc
        return Scenario.from_dict(scenario_raw)

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        self._delete_section_item(
            problem_id,
            ProblemDocumentKey.SCENARIOS,
            ProblemNestedKey.SCENARIO_ID,
            scenario_id,
        )

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def save_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        proposal_data: Proposal,
    ) -> None:
        self._save_section_items(
            problem_id,
            ProblemDocumentKey.PROPOSALS,
            ProblemNestedKey.PROPOSAL_ID,
            proposal_id,
            proposal_data,
        )

    def load_proposals(self, problem_id: str) -> list[Proposal]:
        return self._load_section_items(
            problem_id,
            ProblemDocumentKey.PROPOSALS,
            lambda item: Proposal.from_dict(item),
        )

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        self._delete_section_item(
            problem_id,
            ProblemDocumentKey.PROPOSALS,
            ProblemNestedKey.PROPOSAL_ID,
            proposal_id,
        )

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def save_evaluation(
        self,
        problem_id: str,
        evaluation_id: str,
        evaluation_data: Evaluation,
    ) -> None:
        self._save_section_items(
            problem_id,
            ProblemDocumentKey.EVALUATIONS,
            "evaluation_id",
            evaluation_id,
            evaluation_data,
        )

    def load_evaluations(self, problem_id: str) -> list[Evaluation]:
        return self._load_section_items(
            problem_id,
            ProblemDocumentKey.EVALUATIONS,
            lambda item: Evaluation.from_dict(item),
        )

    def load_evaluation(self, problem_id: str, evaluation_id: str) -> Evaluation:
        problem = self._load_problem_document(problem_id)
        try:
            evaluation_raw = next(
                item
                for item in problem.get(ProblemDocumentKey.EVALUATIONS, [])
                if item.get("evaluation_id") == evaluation_id
            )
        except StopIteration as exc:
            raise FileNotFoundError(evaluation_id) from exc
        return Evaluation.from_dict(evaluation_raw)

    def delete_evaluation(self, problem_id: str, evaluation_id: str) -> None:
        self._delete_section_item(
            problem_id,
            ProblemDocumentKey.EVALUATIONS,
            "evaluation_id",
            evaluation_id,
        )
