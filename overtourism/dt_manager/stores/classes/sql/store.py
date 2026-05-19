# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.classes.sql.orm import (
    SQLBase,
    evaluation_from_orm,
    evaluation_to_orm,
    problem_from_orm,
    problem_to_orm,
    proposal_from_orm,
    proposal_to_orm,
    relationship_from_orm,
    relationship_to_orm,
    scenario_from_orm,
    scenario_to_orm,
)
from overtourism.dt_manager.stores.classes.sql.schema import build_sql_schema
from overtourism.dt_manager.stores.enums import ProblemDocumentKey, ProblemNestedKey
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
    ScenarioDoesNotExist,
)


class SQLStore(Store):
    """SQL implementation of the Store interface using SQLAlchemy."""

    def __init__(self, url: str) -> None:
        self._setup(url)

    def _setup(self, url: str) -> None:
        self.engine = create_engine(url)
        if self.engine.url.get_backend_name() == "sqlite":
            self._enable_sqlite_foreign_keys(self.engine)
        self.schema = build_sql_schema()
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        SQLBase.metadata.create_all(self.engine)

    def _enable_sqlite_foreign_keys(self, engine: Engine) -> None:
        """Enable SQLite foreign key enforcement for each new connection.

        SQLite does not enforce foreign keys unless PRAGMA foreign_keys=ON is
        executed on every connection, so this listener keeps cascades and
        constraints active for the SQL store.
        """

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # ───────────────────────────────────────────────────────────
    # Problems
    # ───────────────────────────────────────────────────────────

    def save_problem(self, problem_id: str, problem_data: dict) -> None:
        with self.session_factory.begin() as session:
            problem_payload = {
                **problem_data,
                ProblemNestedKey.PROBLEM_ID: problem_id,
            }
            session.merge(problem_to_orm(problem_payload))

    def load_problem(self, problem_id: str) -> dict:
        with self.session_factory() as session:
            problem = session.get(self.schema.problems, problem_id)
            if problem is None:
                raise FileNotFoundError(problem_id)
            return problem_from_orm(problem)

    def load_problems(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(self.schema.problems).order_by(self.schema.problems.problem_id)
            ).all()
            return [problem_from_orm(row) for row in rows]

    def delete_problem(self, problem_id: str) -> None:
        with self.session_factory.begin() as session:
            problem = session.get(self.schema.problems, problem_id)
            if problem is not None:
                session.delete(problem)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def save_scenario(
        self,
        problem_id: str,
        scenario_id: str,
        scenario_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            scenario_row = scenario_to_orm(scenario_data, problem_id)
            if (
                scenario_data["scenario_id"] != scenario_id
                or scenario_row.problem_id != problem_id
            ):
                raise ValueError(
                    "Scenario identifiers do not match the provided arguments"
                )
            session.merge(scenario_row)

    def load_scenarios(self, problem_id: str) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(self.schema.scenarios)
                .where(self.schema.scenarios.problem_id == problem_id)
                .order_by(self.schema.scenarios.scenario_id)
            ).all()
            return [scenario_from_orm(row) for row in rows]

    def load_scenario(self, problem_id: str, scenario_id: str) -> dict:
        with self.session_factory() as session:
            row = session.get(self.schema.scenarios, (problem_id, scenario_id))
            if row is None:
                raise ScenarioDoesNotExist(
                    f"Scenario with ID {scenario_id} does not exist"
                )
            return scenario_from_orm(row)

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        with self.session_factory.begin() as session:
            row = session.get(self.schema.scenarios, (problem_id, scenario_id))
            if row is None:
                raise ScenarioDoesNotExist(
                    f"Scenario with ID {scenario_id} does not exist"
                )
            session.delete(row)

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def save_proposal(
        self,
        problem_id: str,
        proposal_id: str,
        proposal_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            proposal_row = proposal_to_orm(proposal_data)
            if (
                proposal_data["proposal_id"] != proposal_id
                or proposal_row.problem_id != problem_id
            ):
                raise ValueError(
                    "Proposal identifiers do not match the provided arguments"
                )
            session.merge(proposal_row)

    def load_proposals(self, problem_id: str) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(self.schema.proposals)
                .where(self.schema.proposals.problem_id == problem_id)
                .order_by(self.schema.proposals.proposal_id)
            ).all()
            return [proposal_from_orm(row) for row in rows]

    def load_proposal(self, problem_id: str, proposal_id: str) -> dict:
        with self.session_factory() as session:
            row = session.get(self.schema.proposals, (problem_id, proposal_id))
            if row is None:
                raise ProposalDoesNotExist(
                    f"Proposal with ID {proposal_id} does not exist"
                )
            return proposal_from_orm(row)

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        with self.session_factory.begin() as session:
            proposal = session.get(self.schema.proposals, (problem_id, proposal_id))
            if proposal is None:
                raise ProposalDoesNotExist(
                    f"Proposal with ID {proposal_id} does not exist"
                )
            session.delete(proposal)

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    def save_relationships(
        self,
        problem_id: str,
        relationships: list[dict[str, str]],
    ) -> None:
        with self.session_factory.begin() as session:
            if session.get(self.schema.problems, problem_id) is None:
                raise FileNotFoundError(problem_id)

            existing_rows = session.scalars(
                select(self.schema.relationships).where(
                    self.schema.relationships.problem_id == problem_id
                )
            ).all()
            for row in existing_rows:
                session.delete(row)
            session.flush()

            for payload in relationships:
                session.add(relationship_to_orm(payload, problem_id))

    def load_relationships(self, problem_id: str) -> list[dict[str, str]]:
        with self.session_factory() as session:
            if session.get(self.schema.problems, problem_id) is None:
                raise FileNotFoundError(problem_id)

            rows = session.scalars(
                select(self.schema.relationships)
                .where(self.schema.relationships.problem_id == problem_id)
                .order_by(
                    self.schema.relationships.proposal_id,
                    self.schema.relationships.scenario_id,
                )
            ).all()
            return [relationship_from_orm(row) for row in rows]

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def save_evaluation(
        self,
        problem_id: str,
        evaluation_id: str,
        evaluation_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            evaluation_row = evaluation_to_orm(evaluation_data, problem_id)
            if (
                evaluation_data["evaluation_id"] != evaluation_id
                or evaluation_row.problem_id != problem_id
            ):
                raise ValueError(
                    "Evaluation identifiers do not match the provided arguments"
                )
            session.merge(evaluation_row)

    def load_evaluations(self, problem_id: str) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(self.schema.evaluations)
                .where(self.schema.evaluations.problem_id == problem_id)
                .order_by(self.schema.evaluations.evaluation_id)
            ).all()
            return [evaluation_from_orm(row) for row in rows]

    def load_evaluation(self, problem_id: str, evaluation_id: str) -> dict:
        with self.session_factory() as session:
            row = session.get(self.schema.evaluations, evaluation_id)
            if row is None or row.problem_id != problem_id:
                raise EvaluationDoesNotExist(
                    f"Evaluation with ID {evaluation_id} does not exist"
                )
            return evaluation_from_orm(row)

    def delete_evaluation(self, problem_id: str, evaluation_id: str) -> None:
        with self.session_factory.begin() as session:
            evaluation = session.get(self.schema.evaluations, evaluation_id)
            if evaluation is None or evaluation.problem_id != problem_id:
                raise EvaluationDoesNotExist(
                    f"Evaluation with ID {evaluation_id} does not exist"
                )
            session.delete(evaluation)

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _save_problem_document(
        self,
        session,
        problem_id: str,
        problem_data: dict,
    ) -> None:
        problem_payload = {
            **problem_data.get(ProblemDocumentKey.PROBLEM, problem_data),
            ProblemNestedKey.PROBLEM_ID: problem_id,
        }
        existing = session.get(self.schema.problems, problem_id)
        if existing is not None:
            session.delete(existing)
            session.flush()

        problem_orm = problem_to_orm(problem_payload)
        problem_orm.proposals = [
            proposal_to_orm(payload)
            for payload in problem_data.get(ProblemDocumentKey.PROPOSALS, [])
        ]
        problem_orm.scenarios = [
            scenario_to_orm(payload, problem_id)
            for payload in problem_data.get(ProblemDocumentKey.SCENARIOS, [])
        ]
        session.add(problem_orm)
        session.flush()
        problem_orm.relationships = [
            relationship_to_orm(payload, problem_id)
            for payload in problem_data.get(ProblemDocumentKey.RELATIONSHIP, [])
        ]
        session.flush()
        problem_orm.evaluations = [
            evaluation_to_orm(payload, problem_id)
            for payload in problem_data.get(ProblemDocumentKey.EVALUATIONS, [])
        ]
