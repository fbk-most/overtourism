# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

import zstandard as zstd
from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    inspect,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import LargeBinary, TypeDecorator

from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.stores.enums import ProblemNestedKey


class SQLBase(DeclarativeBase):
    pass


class CompressedJSON(TypeDecorator[bytes | None]):
    """Persist JSON payloads as compressed binary blobs."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(
        self,
        value: dict[str, Any] | None,
        _dialect: Any,
    ) -> bytes | None:
        if value is None:
            return None
        serialized = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return zstd.ZstdCompressor(level=10).compress(serialized)

    def process_result_value(
        self,
        value: bytes | bytearray | memoryview | str | dict[str, Any] | None,
        _dialect: Any,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return json.loads(value)
        decompressed = zstd.ZstdDecompressor().decompress(bytes(value))
        return json.loads(decompressed.decode("utf-8"))


class ProblemORM(SQLBase):
    __tablename__ = "problems"
    __table_args__ = (Index("ix_problems_tenant_created", "tenant", "created"),)

    tenant: Mapped[str | None] = mapped_column(Text)
    problem_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created: Mapped[str | None] = mapped_column(String)
    updated: Mapped[str | None] = mapped_column(String)
    extras: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    proposals: Mapped[list[ProposalORM]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProposalORM(SQLBase):
    __tablename__ = "proposals"
    __table_args__ = (
        Index("ix_proposals_problem_id_created", "problem_id", "created"),
    )

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE")
    )
    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String)
    created: Mapped[str | None] = mapped_column(String)
    updated: Mapped[str | None] = mapped_column(String)
    extras: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    problem: Mapped[ProblemORM] = relationship(back_populates="proposals")

    relationships: Mapped[list[RelationshipORM]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScenarioORM(SQLBase):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_tenant_created", "tenant", "created"),)

    scenario_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created: Mapped[str | None] = mapped_column(String)
    updated: Mapped[str | None] = mapped_column(String)
    extras: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    index_values: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )

    relationships: Mapped[list[RelationshipORM]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RelationshipORM(SQLBase):
    __tablename__ = "proposal_scenario_relationship"
    __table_args__ = (
        Index(
            "ix_proposal_scenario_relationship_scenario_id",
            "scenario_id",
        ),
    )

    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.proposal_id", ondelete="CASCADE"), primary_key=True
    )
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("scenarios.scenario_id", ondelete="CASCADE"), primary_key=True
    )


class EvaluationORM(SQLBase):
    __tablename__ = "evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            ondelete="CASCADE",
        ),
        Index("ix_evaluations_scenario_id_started", "scenario_id", "started"),
    )

    evaluation_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    started: Mapped[str | None] = mapped_column(String)
    finished: Mapped[str | None] = mapped_column(String)
    result: Mapped[dict[str, Any] | None] = mapped_column(
        CompressedJSON(),
        nullable=True,
    )


def orm_to_dict(entity: Any) -> dict[str, Any]:
    return {
        attr.key: getattr(entity, attr.key)
        for attr in inspect(entity).mapper.column_attrs
    }


def problem_to_orm(problem: dict[str, Any]) -> ProblemORM:
    return ProblemORM(
        problem_id=problem["problem_id"],
        version=problem.get("version", 0),
        tenant=problem.get("tenant"),
        name=problem.get("name"),
        description=problem.get("description"),
        created=problem.get("created"),
        updated=problem.get("updated"),
        extras=problem.get("extras", {}),
    )


def problem_from_orm(problem: ProblemORM) -> dict[str, Any]:
    return orm_to_dict(problem)


def proposal_to_orm(proposal: dict[str, Any]) -> ProposalORM:
    return ProposalORM(
        problem_id=proposal.get("problem_id", ""),
        proposal_id=proposal["proposal_id"],
        version=proposal.get("version", 0),
        name=proposal.get("name"),
        description=proposal.get("description"),
        status=proposal.get("status"),
        created=proposal.get("created"),
        updated=proposal.get("updated"),
        extras=proposal.get("extras", {}),
    )


def proposal_from_orm(proposal: ProposalORM) -> dict[str, Any]:
    return orm_to_dict(proposal)


def scenario_to_orm(scenario: dict[str, Any]) -> ScenarioORM:
    index_values = scenario.get("index_values", [])
    return ScenarioORM(
        scenario_id=scenario["scenario_id"],
        tenant=scenario["tenant"],
        version=scenario.get("version", 0),
        name=scenario.get("name"),
        description=scenario.get("description"),
        created=scenario.get("created"),
        updated=scenario.get("updated"),
        extras=scenario.get("extras", {}),
        index_values=[
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in index_values
        ],
    )


def scenario_from_orm(scenario: ScenarioORM) -> dict[str, Any]:
    return orm_to_dict(scenario)


def relationship_to_orm(payload: dict) -> RelationshipORM:
    return RelationshipORM(
        proposal_id=payload[ProblemNestedKey.PROPOSAL_ID],
        scenario_id=payload[ProblemNestedKey.SCENARIO_ID],
    )


def relationship_from_orm(relationship: RelationshipORM) -> dict[str, str]:
    return {
        ProblemNestedKey.PROPOSAL_ID.value: relationship.proposal_id,
        ProblemNestedKey.SCENARIO_ID.value: relationship.scenario_id,
    }


def evaluation_to_orm(evaluation: dict[str, Any]) -> EvaluationORM:
    result = evaluation.get("result")
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if result is not None and not isinstance(result, dict):
        raise TypeError(
            "Evaluation result must be JSON-serializable or expose to_dict()"
        )
    state = evaluation.get("state", EvaluationState.RUNNING)
    if isinstance(state, EvaluationState):
        state = state.value
    return EvaluationORM(
        evaluation_id=evaluation["evaluation_id"],
        version=evaluation.get("version", 0),
        scenario_id=evaluation["scenario_id"],
        type=evaluation["type"],
        state=state,
        started=evaluation.get("started"),
        finished=evaluation.get("finished"),
        result=result,
    )


def evaluation_from_orm(evaluation: EvaluationORM) -> dict[str, Any]:
    return orm_to_dict(evaluation)
