# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.classes.local.io import load_json, save_json
from overtourism.dt_manager.stores.enums import ProblemDocumentKey
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ScenarioDoesNotExist,
)


class LocalIOStore(Store):
    """Local filesystem implementation of the Store interface."""

    def __init__(self, folder: str) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def save_problem(self, problem_id: str, problem_data: dict) -> None:
        self.save_problem_document(
            problem_id, self._normalize_problem_document(problem_data)
        )

    def load_problem_document(self, problem_id: str) -> dict:
        return self._compose_problem_document(problem_id)

    def save_problem_document(self, problem_id: str, problem_data: dict) -> None:
        document = self._normalize_problem_document(problem_data)
        self._write_problem_document(problem_id, document)

    def load_problem(self, problem_id: str) -> Problem:
        path = self._problem_file(problem_id)
        if not path.exists():
            raise FileNotFoundError(problem_id)
        return Problem.from_dict(load_json(path))

    def list_problems(self) -> list[str]:
        problems_dir = self.folder / "problems"
        if not problems_dir.exists():
            return []
        return [path.stem for path in sorted(problems_dir.glob("*.json"))]

    def delete_problem(self, problem_id: str) -> None:
        self._delete_problem_file(problem_id)
        self._delete_collection_dir(self._scenarios_dir(problem_id))
        self._delete_collection_dir(self._proposals_dir(problem_id))
        self._delete_collection_dir(self._evaluations_dir(problem_id))
        self._delete_relationship_file(problem_id)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def save_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        scenario_data: Scenario,
    ) -> None:
        if scenario_data.scenario_id != scenario_id:
            raise ValueError("Scenario identifiers do not match the provided arguments")
        scenario_data.problem_id = problem_id
        save_json(scenario_data.to_dict(), self._scenario_file(problem_id, scenario_id))

    def load_scenarios(self, problem_id: str) -> list[Scenario]:
        return [
            Scenario.from_dict(load_json(path))
            for path in self._entity_files(self._scenarios_dir(problem_id))
        ]

    def load_scenario(self, problem_id: str, scenario_id: str) -> Scenario:
        path = self._scenario_file(problem_id, scenario_id)
        if not path.exists():
            raise ScenarioDoesNotExist(f"Scenario with ID {scenario_id} does not exist")
        return Scenario.from_dict(load_json(path))

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        self._delete_file(self._scenario_file(problem_id, scenario_id))

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def save_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        proposal_data: Proposal,
    ) -> None:
        if proposal_data.proposal_id != proposal_id:
            raise ValueError("Proposal identifiers do not match the provided arguments")
        proposal_data.problem_id = problem_id
        save_json(proposal_data.to_dict(), self._proposal_file(problem_id, proposal_id))

    def load_proposals(self, problem_id: str) -> list[Proposal]:
        return [
            Proposal.from_dict(load_json(path))
            for path in self._entity_files(self._proposals_dir(problem_id))
        ]

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        self._delete_file(self._proposal_file(problem_id, proposal_id))

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def save_evaluation(
        self,
        problem_id: str,
        evaluation_id: str,
        evaluation_data: Evaluation,
    ) -> None:
        if evaluation_data.evaluation_id != evaluation_id:
            raise ValueError(
                "Evaluation identifiers do not match the provided arguments"
            )
        save_json(
            evaluation_data.to_dict(),
            self._evaluation_file(problem_id, evaluation_id),
        )

    def load_evaluations(self, problem_id: str) -> list[Evaluation]:
        return [
            Evaluation.from_dict(load_json(path))
            for path in self._entity_files(self._evaluations_dir(problem_id))
        ]

    def load_evaluation(self, problem_id: str, evaluation_id: str) -> Evaluation:
        path = self._evaluation_file(problem_id, evaluation_id)
        if not path.exists():
            raise EvaluationDoesNotExist(
                f"Evaluation with ID {evaluation_id} does not exist"
            )
        return Evaluation.from_dict(load_json(path))

    def delete_evaluation(self, problem_id: str, evaluation_id: str) -> None:
        self._delete_file(self._evaluation_file(problem_id, evaluation_id))

    # ───────────────────────────────────────────────────────────
    # Internal helpers
    # ───────────────────────────────────────────────────────────

    def _normalize_problem_document(self, problem_data: dict) -> dict:
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

    def _compose_problem_document(self, problem_id: str) -> dict:
        problem_path = self._problem_file(problem_id)
        if not problem_path.exists():
            raise FileNotFoundError(problem_id)
        return {
            ProblemDocumentKey.PROBLEM: load_json(problem_path),
            ProblemDocumentKey.SCENARIOS: [
                load_json(path)
                for path in self._entity_files(self._scenarios_dir(problem_id))
            ],
            ProblemDocumentKey.PROPOSALS: [
                load_json(path)
                for path in self._entity_files(self._proposals_dir(problem_id))
            ],
            ProblemDocumentKey.EVALUATIONS: [
                load_json(path)
                for path in self._entity_files(self._evaluations_dir(problem_id))
            ],
            ProblemDocumentKey.RELATIONSHIP: self._load_relationships(problem_id),
        }

    def _write_problem_document(self, problem_id: str, problem_data: dict) -> None:
        save_json(
            problem_data[ProblemDocumentKey.PROBLEM], self._problem_file(problem_id)
        )
        self._write_collection(
            self._scenarios_dir(problem_id),
            problem_data.get(ProblemDocumentKey.SCENARIOS, []),
            lambda item: item["scenario_id"],
        )
        self._write_collection(
            self._proposals_dir(problem_id),
            problem_data.get(ProblemDocumentKey.PROPOSALS, []),
            lambda item: item["proposal_id"],
        )
        self._write_collection(
            self._evaluations_dir(problem_id),
            problem_data.get(ProblemDocumentKey.EVALUATIONS, []),
            lambda item: item["evaluation_id"],
        )
        save_json(
            problem_data.get(ProblemDocumentKey.RELATIONSHIP, []),
            self._relationship_file(problem_id),
        )

    def _write_collection(self, root: Path, items: list[dict], key_getter) -> None:
        self._delete_collection_dir(root)
        root.mkdir(parents=True, exist_ok=True)
        for item in items:
            save_json(item, root / f"{key_getter(item)}.json")

    def _load_relationships(self, problem_id: str) -> list[dict]:
        path = self._relationship_file(problem_id)
        if not path.exists():
            return []
        relationships = load_json(path)
        return relationships if isinstance(relationships, list) else []

    def _problem_file(self, problem_id: str) -> Path:
        return self.folder / "problems" / f"{problem_id}.json"

    def _scenarios_dir(self, problem_id: str) -> Path:
        return self.folder / "scenarios" / problem_id

    def _scenario_file(self, problem_id: str, scenario_id: str) -> Path:
        return self._scenarios_dir(problem_id) / f"{scenario_id}.json"

    def _proposals_dir(self, problem_id: str) -> Path:
        return self.folder / "proposals" / problem_id

    def _proposal_file(self, problem_id: str, proposal_id: str) -> Path:
        return self._proposals_dir(problem_id) / f"{proposal_id}.json"

    def _evaluations_dir(self, problem_id: str) -> Path:
        return self.folder / "evaluations" / problem_id

    def _evaluation_file(self, problem_id: str, evaluation_id: str) -> Path:
        return self._evaluations_dir(problem_id) / f"{evaluation_id}.json"

    def _relationship_file(self, problem_id: str) -> Path:
        return self.folder / "relationships" / f"{problem_id}.json"

    def _entity_files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return [path for path in sorted(root.glob("*.json"))]

    def _delete_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def _delete_problem_file(self, problem_id: str) -> None:
        self._delete_file(self._problem_file(problem_id))

    def _delete_collection_dir(self, root: Path) -> None:
        if root.exists():
            rmtree(root)

    def _delete_relationship_file(self, problem_id: str) -> None:
        self._delete_file(self._relationship_file(problem_id))
