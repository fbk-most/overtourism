# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, String, Text, inspect
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from overtourism.dt_manager.evaluation.evaluation import EvaluationState
from overtourism.dt_manager.stores.enums import ProblemNestedKey


class SQLBase(DeclarativeBase):
    pass


class ProblemORM(SQLBase):
    __tablename__ = "problems"

    problem_id: Mapped[str] = mapped_column(String, primary_key=True)
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
    scenarios: Mapped[list[ScenarioORM]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    evaluations: Mapped[list[EvaluationORM]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    relationships: Mapped[list[RelationshipORM]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProposalORM(SQLBase):
    __tablename__ = "proposals"

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        primary_key=True,
    )
    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
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


class ScenarioORM(SQLBase):
    __tablename__ = "scenarios"

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        primary_key=True,
    )
    scenario_id: Mapped[str] = mapped_column(String, primary_key=True)
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
    problem: Mapped[ProblemORM] = relationship(back_populates="scenarios")


class RelationshipORM(SQLBase):
    __tablename__ = "proposal_scenario_relationship"

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        primary_key=True,
    )
    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String, primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["problem_id", "proposal_id"],
            ["proposals.problem_id", "proposals.proposal_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["problem_id", "scenario_id"],
            ["scenarios.problem_id", "scenarios.scenario_id"],
            ondelete="CASCADE",
        ),
    )


class EvaluationORM(SQLBase):
    __tablename__ = "evaluations"

    evaluation_id: Mapped[str] = mapped_column(String, primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    started: Mapped[str | None] = mapped_column(String)
    finished: Mapped[str | None] = mapped_column(String)
    result: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    problem: Mapped[ProblemORM] = relationship(back_populates="evaluations")

    __table_args__ = (
        ForeignKeyConstraint(
            ["problem_id", "scenario_id"],
            ["scenarios.problem_id", "scenarios.scenario_id"],
            ondelete="CASCADE",
        ),
    )


def orm_to_dict(entity: Any) -> dict[str, Any]:
    return {
        attr.key: getattr(entity, attr.key)
        for attr in inspect(entity).mapper.column_attrs
    }


def problem_to_orm(problem: dict[str, Any]) -> ProblemORM:
    return ProblemORM(
        problem_id=problem["problem_id"],
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
        name=proposal.get("name"),
        description=proposal.get("description"),
        status=proposal.get("status"),
        created=proposal.get("created"),
        updated=proposal.get("updated"),
        extras=proposal.get("extras", {}),
    )


def proposal_from_orm(proposal: ProposalORM) -> dict[str, Any]:
    return orm_to_dict(proposal)


def scenario_to_orm(
    scenario: dict[str, Any], problem_id: str | None = None
) -> ScenarioORM:
    index_values = scenario.get("index_values", [])
    return ScenarioORM(
        problem_id=problem_id or scenario.get("problem_id", ""),
        scenario_id=scenario["scenario_id"],
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


def relationship_to_orm(payload: dict, problem_id: str) -> RelationshipORM:
    return RelationshipORM(
        problem_id=problem_id,
        proposal_id=payload[ProblemNestedKey.PROPOSAL_ID],
        scenario_id=payload[ProblemNestedKey.SCENARIO_ID],
    )


def relationship_from_orm(relationship: RelationshipORM) -> dict[str, str]:
    return {
        ProblemNestedKey.PROPOSAL_ID.value: relationship.proposal_id,
        ProblemNestedKey.SCENARIO_ID.value: relationship.scenario_id,
    }


def evaluation_to_orm(
    evaluation: dict[str, Any], problem_id: str | None = None
) -> EvaluationORM:
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
        problem_id=problem_id
        or evaluation.get("problem_id")
        or evaluation["scenario_id"].split("_")[0],
        scenario_id=evaluation["scenario_id"],
        type=evaluation["type"],
        state=state,
        started=evaluation.get("started"),
        finished=evaluation.get("finished"),
        result=result,
    )


def evaluation_from_orm(evaluation: EvaluationORM) -> dict[str, Any]:
    return orm_to_dict(evaluation)
