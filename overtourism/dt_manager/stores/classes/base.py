# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod


class Store(ABC):
    """Abstract base for problem, scenario, and proposal persistence.

    Implementations are responsible for storing the serialized problem
    document and its nested scenarios and proposals.
    """

    @abstractmethod
    def save_problem(self, problem_id: str, problem_data: dict) -> None:
        """Persist a problem document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to save.
        problem_data : dict
            Serialized problem payload.
        """
        ...

    @abstractmethod
    def load_problem_document(self, problem_id: str) -> dict:
        """Load the raw problem document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to load.

        Returns
        -------
        dict
            Raw problem payload.
        """
        ...

    @abstractmethod
    def save_problem_document(self, problem_id: str, problem_data: dict) -> None:
        """Persist a raw problem document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to save.
        problem_data : dict
            Raw problem payload.
        """
        ...

    @abstractmethod
    def load_problem(self, problem_id: str) -> dict:
        """Load a problem document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to load.

        Returns
        -------
        dict
            Loaded problem payload.
        """
        ...

    @abstractmethod
    def list_problems(self) -> list[str]:
        """Return all stored problem identifiers.

        Returns
        -------
        list[str]
            Stored problem identifiers.
        """
        ...

    @abstractmethod
    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem document.

        Parameters
        ----------
        problem_id : str
            Identifier of the problem to delete.
        """
        ...

    @abstractmethod
    def load_scenarios(self, problem_id: str) -> list[dict]:
        """Load all scenarios for a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.

        Returns
        -------
        list[dict]
            Loaded scenario payloads.
        """
        ...

    @abstractmethod
    def save_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        scenario_data: dict,
    ) -> None:
        """Persist a scenario document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        scenario_id : str
            Identifier of the scenario to save.
        scenario_data : dict
            Serialized scenario payload.
        """
        ...

    @abstractmethod
    def load_scenario(self, problem_id: str, scenario_id: str) -> dict:
        """Load a single scenario.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        scenario_id : str
            Identifier of the scenario to load.

        Returns
        -------
        dict
            Loaded scenario payload.
        """
        ...

    @abstractmethod
    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        """Delete a scenario document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        scenario_id : str
            Identifier of the scenario to delete.
        """
        ...

    @abstractmethod
    def save_proposal(
        self, problem_id: str, proposal_id: str, proposal_data: dict
    ) -> None:
        """Persist a proposal document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        proposal_id : str
            Identifier of the proposal to save.
        proposal_data : dict
            Serialized proposal payload.
        """
        ...

    @abstractmethod
    def load_proposals(self, problem_id: str) -> list[dict]:
        """Load all proposals for a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.

        Returns
        -------
        list[dict]
            Loaded proposal payloads.
        """
        ...

    @abstractmethod
    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        """Delete a proposal document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        proposal_id : str
            Identifier of the proposal to delete.
        """
        ...

    @abstractmethod
    def save_evaluation(
        self,
        problem_id: str,
        evaluation_id: str,
        evaluation_data: dict,
    ) -> None:
        """Persist an evaluation document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        evaluation_id : str
            Identifier of the evaluation to save.
        evaluation_data : dict
            Serialized evaluation payload.
        """
        ...

    @abstractmethod
    def load_evaluations(self, problem_id: str) -> list[dict]:
        """Load all evaluations for a problem.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.

        Returns
        -------
        list[dict]
            Loaded evaluation payloads.
        """
        ...

    @abstractmethod
    def load_evaluation(self, problem_id: str, evaluation_id: str) -> dict:
        """Load a single evaluation.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        evaluation_id : str
            Identifier of the evaluation to load.

        Returns
        -------
        dict
            Loaded evaluation payload.
        """
        ...

    @abstractmethod
    def delete_evaluation(self, problem_id: str, evaluation_id: str) -> None:
        """Delete an evaluation document.

        Parameters
        ----------
        problem_id : str
            Identifier of the parent problem.
        evaluation_id : str
            Identifier of the evaluation to delete.
        """
        ...
