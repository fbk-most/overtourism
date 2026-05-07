# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass

from .orm import (
    EvaluationORM,
    ExecutionORM,
    ProblemORM,
    ProposalORM,
    RelationshipORM,
    ScenarioORM,
)


@dataclass
class SQLSchema:
    problems: type[ProblemORM]
    proposals: type[ProposalORM]
    scenarios: type[ScenarioORM]
    evaluations: type[EvaluationORM]
    relationships: type[RelationshipORM]
    executions: type[ExecutionORM]


def build_sql_schema() -> SQLSchema:
    return SQLSchema(
        problems=ProblemORM,
        proposals=ProposalORM,
        scenarios=ScenarioORM,
        evaluations=EvaluationORM,
        relationships=RelationshipORM,
        executions=ExecutionORM,
    )
