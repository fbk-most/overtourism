# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass

from .orm import (
    EvaluationORM,
    ProblemORM,
    ProposalORM,
    RelationshipORM,
    ScenarioORM,
    SessionORM,
)


@dataclass
class SQLSchema:
    sessions: type[SessionORM]
    problems: type[ProblemORM]
    proposals: type[ProposalORM]
    scenarios: type[ScenarioORM]
    evaluations: type[EvaluationORM]
    relationships: type[RelationshipORM]


def build_sql_schema() -> SQLSchema:
    return SQLSchema(
        sessions=SessionORM,
        problems=ProblemORM,
        proposals=ProposalORM,
        scenarios=ScenarioORM,
        evaluations=EvaluationORM,
        relationships=RelationshipORM,
    )
