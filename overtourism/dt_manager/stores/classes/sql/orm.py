# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from overtourism.dt_manager.classes.indexes import IndexEntry
from overtourism.dt_manager.evaluation.evaluation import Evaluation, EvaluationState
from overtourism.dt_manager.problem.problem import Problem
from overtourism.dt_manager.proposal.proposal import Proposal
from overtourism.dt_manager.scenario.scenario import Scenario
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
    index_diffs: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    index_values: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    is_evaluating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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


class ExecutionORM(SQLBase):
    __tablename__ = "execution"

    execution_id: Mapped[str] = mapped_column(String, primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    output_data: Mapped[str | None] = mapped_column(Text)
    output_link: Mapped[str | None] = mapped_column(Text)
    created: Mapped[str | None] = mapped_column(String)
    updated: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
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


def problem_to_orm(problem: Problem) -> ProblemORM:
    return ProblemORM(
        problem_id=problem.problem_id,
        name=problem.name,
        description=problem.description,
        created=problem.created,
        updated=problem.updated,
        extras=problem.extras,
    )


def problem_from_orm(problem: ProblemORM) -> Problem:
    return Problem(
        problem_id=problem.problem_id,
        name=problem.name,
        description=problem.description,
        created=problem.created,
        updated=problem.updated,
        extras=problem.extras,
    )


def proposal_to_orm(proposal: Proposal) -> ProposalORM:
    return ProposalORM(
        problem_id=proposal.problem_id,
        proposal_id=proposal.proposal_id,
        name=proposal.name,
        description=proposal.description,
        status=proposal.status,
        created=proposal.created,
        updated=proposal.updated,
        extras=proposal.extras,
    )


def proposal_from_orm(proposal: ProposalORM) -> Proposal:
    return Proposal(
        proposal_id=proposal.proposal_id,
        problem_id=proposal.problem_id,
        name=proposal.name,
        description=proposal.description,
        status=proposal.status,
        created=proposal.created,
        updated=proposal.updated,
        extras=proposal.extras,
    )


def scenario_to_orm(scenario: Scenario, problem_id: str | None = None) -> ScenarioORM:
    return ScenarioORM(
        problem_id=problem_id or scenario.problem_id,
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        description=scenario.description,
        created=scenario.created,
        updated=scenario.updated,
        extras=scenario.extras,
        index_diffs=scenario.index_diffs,
        index_values=[item.to_dict() for item in scenario.index_values],
        is_evaluating=scenario.is_evaluating,
    )


def scenario_from_orm(scenario: ScenarioORM) -> Scenario:
    return Scenario(
        scenario_id=scenario.scenario_id,
        problem_id=scenario.problem_id,
        name=scenario.name,
        description=scenario.description,
        created=scenario.created,
        updated=scenario.updated,
        index_diffs=scenario.index_diffs,
        extras=scenario.extras,
        index_values=[IndexEntry.from_dict(item) for item in scenario.index_values],
        is_evaluating=scenario.is_evaluating,
    )


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
    evaluation: Evaluation, problem_id: str | None = None
) -> EvaluationORM:
    result = evaluation.result
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if result is not None and not isinstance(result, dict):
        raise TypeError(
            "Evaluation result must be JSON-serializable or expose to_dict()"
        )
    return EvaluationORM(
        evaluation_id=evaluation.evaluation_id,
        problem_id=problem_id or evaluation.scenario_id.split("_")[0],
        scenario_id=evaluation.scenario_id,
        type=evaluation.type,
        state=evaluation.state.value,
        started=evaluation.started,
        finished=evaluation.finished,
        result=result,
    )


def evaluation_from_orm(evaluation: EvaluationORM) -> Evaluation:
    return Evaluation(
        evaluation_id=evaluation.evaluation_id,
        scenario_id=evaluation.scenario_id,
        type=evaluation.type,
        state=EvaluationState(evaluation.state),
        started=evaluation.started,
        finished=evaluation.finished,
        result=evaluation.result,
    )
