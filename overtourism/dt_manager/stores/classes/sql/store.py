# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, TypeVar

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

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
from overtourism.dt_manager.stores.enums import ProblemNestedKey
from overtourism.dt_manager.utils.exception import (
    EvaluationDoesNotExist,
    ProposalDoesNotExist,
    ScenarioDoesNotExist,
)


class _ScopedEntityRow(Protocol):
    problem_id: str


ScopedEntityRowT = TypeVar("ScopedEntityRowT", bound=_ScopedEntityRow)


class SQLStore(Store):
    """SQL implementation of the Store interface using SQLAlchemy."""

    def __init__(self, url: str) -> None:
        self._setup(url)

    def _setup(self, url: str) -> None:
        self._ensure_sqlite_parent_dirs(url)
        self.engine = create_engine(url)
        if self.engine.url.get_backend_name() == "sqlite":
            self._enable_sqlite_foreign_keys(self.engine)
        self.schema = build_sql_schema()
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        SQLBase.metadata.create_all(self.engine)

    def _ensure_sqlite_parent_dirs(self, url: str) -> None:
        parsed_url = make_url(url)
        if parsed_url.get_backend_name() != "sqlite":
            return

        database = parsed_url.database
        if database in (None, "", ":memory:"):
            return

        Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

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
            self._merge_scoped_entity(
                session,
                entity_name="Scenario",
                problem_id=problem_id,
                entity_id=scenario_id,
                payload=scenario_data,
                payload_id_key="scenario_id",
                entity_row=scenario_to_orm(scenario_data, problem_id),
            )

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
            row = self._load_scoped_row_or_raise(
                session,
                self.schema.scenarios,
                (problem_id, scenario_id),
                entity_name="Scenario",
                entity_id=scenario_id,
                problem_id=problem_id,
                exception_type=ScenarioDoesNotExist,
            )
            return scenario_from_orm(row)

    def delete_scenario(self, problem_id: str, scenario_id: str) -> None:
        with self.session_factory.begin() as session:
            row = self._load_scoped_row_or_raise(
                session,
                self.schema.scenarios,
                (problem_id, scenario_id),
                entity_name="Scenario",
                entity_id=scenario_id,
                problem_id=problem_id,
                exception_type=ScenarioDoesNotExist,
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
            self._merge_scoped_entity(
                session,
                entity_name="Proposal",
                problem_id=problem_id,
                entity_id=proposal_id,
                payload=proposal_data,
                payload_id_key="proposal_id",
                entity_row=proposal_to_orm(proposal_data),
            )

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
            row = self._load_scoped_row_or_raise(
                session,
                self.schema.proposals,
                (problem_id, proposal_id),
                entity_name="Proposal",
                entity_id=proposal_id,
                problem_id=problem_id,
                exception_type=ProposalDoesNotExist,
            )
            return proposal_from_orm(row)

    def delete_proposal(self, problem_id: str, proposal_id: str) -> None:
        with self.session_factory.begin() as session:
            proposal = self._load_scoped_row_or_raise(
                session,
                self.schema.proposals,
                (problem_id, proposal_id),
                entity_name="Proposal",
                entity_id=proposal_id,
                problem_id=problem_id,
                exception_type=ProposalDoesNotExist,
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
            self._merge_scoped_entity(
                session,
                entity_name="Evaluation",
                problem_id=problem_id,
                entity_id=evaluation_id,
                payload=evaluation_data,
                payload_id_key="evaluation_id",
                entity_row=evaluation_to_orm(evaluation_data, problem_id),
            )

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
            row = self._load_scoped_row_or_raise(
                session,
                self.schema.evaluations,
                evaluation_id,
                entity_name="Evaluation",
                entity_id=evaluation_id,
                problem_id=problem_id,
                exception_type=EvaluationDoesNotExist,
            )
            return evaluation_from_orm(row)

    def delete_evaluation(self, problem_id: str, evaluation_id: str) -> None:
        with self.session_factory.begin() as session:
            evaluation = self._load_scoped_row_or_raise(
                session,
                self.schema.evaluations,
                evaluation_id,
                entity_name="Evaluation",
                entity_id=evaluation_id,
                problem_id=problem_id,
                exception_type=EvaluationDoesNotExist,
            )
            session.delete(evaluation)

    # ───────────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────────

    def _merge_scoped_entity(
        self,
        session: Session,
        *,
        entity_name: str,
        problem_id: str,
        entity_id: str,
        payload: Mapping[str, object],
        payload_id_key: str,
        entity_row: _ScopedEntityRow,
    ) -> None:
        if payload[payload_id_key] != entity_id or entity_row.problem_id != problem_id:
            raise ValueError(
                f"{entity_name} identifiers do not match the provided arguments"
            )
        session.merge(entity_row)

    def _load_scoped_row_or_raise(
        self,
        session: Session,
        orm_model: type[ScopedEntityRowT],
        primary_key: object,
        *,
        entity_name: str,
        entity_id: str,
        problem_id: str,
        exception_type: type[Exception],
    ) -> ScopedEntityRowT:
        row = session.get(orm_model, primary_key)
        if row is None or row.problem_id != problem_id:
            raise exception_type(f"{entity_name} with ID {entity_id} does not exist")
        return row
