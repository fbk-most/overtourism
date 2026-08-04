# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, event, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from overtourism.dt_manager.stores.classes.base import Store
from overtourism.dt_manager.stores.classes.sql.orm import (
    EvaluationORM,
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
from overtourism.dt_manager.utils.exception import EntityDoesNotExist


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
        self._migrate_evaluation_result_column_if_needed()

    def _migrate_evaluation_result_column_if_needed(self) -> None:
        if self.engine.dialect.name not in {"sqlite", "postgresql"}:
            return

        with self.engine.begin() as connection:
            inspector = inspect(connection)
            column_info = next(
                (
                    column
                    for column in inspector.get_columns("evaluations")
                    if column["name"] == "result"
                ),
                None,
            )

            if column_info is None:
                return

            column_type_name = column_info["type"].__class__.__name__.lower()
            if column_type_name in {"largebinary", "blob", "bytea"}:
                return

            connection.exec_driver_sql("DROP TABLE IF EXISTS evaluations_legacy")
            connection.exec_driver_sql(
                "ALTER TABLE evaluations RENAME TO evaluations_legacy"
            )
            connection.exec_driver_sql(
                "DROP INDEX IF EXISTS ix_evaluations_scenario_id_started"
            )
            EvaluationORM.__table__.create(connection)

            legacy_table = Table(
                "evaluations_legacy",
                MetaData(),
                autoload_with=connection,
            )
            rows = connection.execute(select(legacy_table)).mappings().all()
            if rows:
                connection.execute(
                    EvaluationORM.__table__.insert(), [dict(row) for row in rows]
                )

            connection.exec_driver_sql("DROP TABLE evaluations_legacy")

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

    def save_problem(self, problem_data: dict) -> None:
        with self.session_factory.begin() as session:
            session.merge(problem_to_orm(problem_data))

    def load_problem(self, problem_id: str) -> dict:
        with self.session_factory() as session:
            problem = session.get(self.schema.problems, problem_id)
            if problem is None:
                raise EntityDoesNotExist(f"Problem '{problem_id}' not found")
            return problem_from_orm(problem)

    def load_problems(self, tenant: str | None = None) -> list[dict]:
        with self.session_factory() as session:
            query = select(self.schema.problems)
            if tenant is not None:
                query = query.where(self.schema.problems.tenant == tenant)
            query = query.order_by(
                self.schema.problems.created.desc(),
                self.schema.problems.problem_id.asc(),
            )
            rows = session.scalars(query).all()
            return [problem_from_orm(row) for row in rows]

    def delete_problem(self, problem_id: str) -> None:
        with self.session_factory.begin() as session:
            problem = session.get(self.schema.problems, problem_id)
            if problem is not None:
                session.delete(problem)

    # ───────────────────────────────────────────────────────────
    # Proposals
    # ───────────────────────────────────────────────────────────

    def save_proposal(
        self,
        proposal_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            session.merge(proposal_to_orm(proposal_data))

    def load_proposals(
        self,
        problem_id: str | None = None,
        scenario_id: str | None = None,
    ) -> list[dict]:
        with self.session_factory() as session:
            query = select(self.schema.proposals)
            if problem_id is not None:
                query = query.where(self.schema.proposals.problem_id == problem_id)
            if scenario_id is not None:
                query_proposal_ids = select(
                    self.schema.relationships.proposal_id
                ).where(self.schema.relationships.scenario_id == scenario_id)
                query = query.where(
                    self.schema.proposals.proposal_id.in_(query_proposal_ids)
                )
            query = query.order_by(
                self.schema.proposals.created.desc(),
                self.schema.proposals.proposal_id.asc(),
            )
            rows = session.scalars(query).all()
            return [proposal_from_orm(row) for row in rows]

    def load_proposal(self, proposal_id: str) -> dict:
        with self.session_factory() as session:
            proposal = session.get(self.schema.proposals, proposal_id)
            if proposal is None:
                raise EntityDoesNotExist(f"Proposal '{proposal_id}' not found")
            return proposal_from_orm(proposal)

    def delete_proposal(self, proposal_id: str) -> None:
        with self.session_factory.begin() as session:
            proposal = session.get(self.schema.proposals, proposal_id)
            if proposal is not None:
                session.delete(proposal)

    # ───────────────────────────────────────────────────────────
    # Scenarios
    # ───────────────────────────────────────────────────────────

    def save_scenario(
        self,
        scenario_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            session.merge(scenario_to_orm(scenario_data))

    def load_scenarios(
        self, tenant: str | None = None, proposal_id: str | None = None
    ) -> list[dict]:
        with self.session_factory() as session:
            query = select(self.schema.scenarios)
            if tenant is not None:
                query = query.where(self.schema.scenarios.tenant == tenant)
            if proposal_id is not None:
                query_scenario_ids = select(
                    self.schema.relationships.scenario_id
                ).where(self.schema.relationships.proposal_id == proposal_id)
                query = query.where(
                    self.schema.scenarios.scenario_id.in_(query_scenario_ids)
                )
            query = query.order_by(
                self.schema.scenarios.created.desc(),
                self.schema.scenarios.scenario_id.asc(),
            )
            rows = session.scalars(query).all()
            return [scenario_from_orm(row) for row in rows]

    def load_scenario(self, scenario_id: str) -> dict:
        with self.session_factory() as session:
            scenario = session.get(self.schema.scenarios, scenario_id)
            if scenario is None:
                raise EntityDoesNotExist(f"Scenario '{scenario_id}' not found")
            return scenario_from_orm(scenario)

    def delete_scenario(self, scenario_id: str) -> None:
        with self.session_factory.begin() as session:
            scenario = session.get(self.schema.scenarios, scenario_id)
            if scenario is not None:
                session.delete(scenario)

    # ───────────────────────────────────────────────────────────
    # Evaluations
    # ───────────────────────────────────────────────────────────

    def save_evaluation(
        self,
        evaluation_data: dict,
    ) -> None:
        with self.session_factory.begin() as session:
            session.merge(evaluation_to_orm(evaluation_data))

    def load_evaluations(self, scenario_id: str | None = None) -> list[dict]:
        with self.session_factory() as session:
            query = select(self.schema.evaluations)
            if scenario_id is not None:
                query = query.where(self.schema.evaluations.scenario_id == scenario_id)
            rows = session.scalars(
                query.order_by(
                    self.schema.evaluations.started.desc(),
                    self.schema.evaluations.evaluation_id.asc(),
                )
            ).all()
            return [evaluation_from_orm(row) for row in rows]

    def load_evaluation(self, evaluation_id: str) -> dict:
        with self.session_factory() as session:
            evaluation = session.get(self.schema.evaluations, evaluation_id)
            if evaluation is None:
                raise EntityDoesNotExist(f"Evaluation '{evaluation_id}' not found")
            return evaluation_from_orm(evaluation)

    def delete_evaluation(self, evaluation_id: str) -> None:
        with self.session_factory.begin() as session:
            evaluation = session.get(self.schema.evaluations, evaluation_id)
            if evaluation is not None:
                session.delete(evaluation)

    # ───────────────────────────────────────────────────────────
    # Relationships
    # ───────────────────────────────────────────────────────────

    def save_relationships(self, relationships: list[dict[str, str]]) -> None:
        with self.session_factory.begin() as session:
            for relationship_data in relationships:
                session.merge(relationship_to_orm(relationship_data))

    def load_relationships(self) -> list[dict[str, str]]:
        with self.session_factory() as session:
            query = select(self.schema.relationships)
            rows = session.scalars(query).all()
            return [relationship_from_orm(row) for row in rows]
