# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum


class StoreType(StrEnum):
    """Supported storage backend types."""

    LOCAL = "local"
    SQL = "sql"


class ProblemDocumentKey(StrEnum):
    """Top-level keys in stored problem documents."""

    PROBLEM = "problem"
    SCENARIOS = "scenarios"
    PROPOSALS = "proposals"
    EVALUATIONS = "evaluations"
    RELATIONSHIP = "relationship"


class ProblemNestedKey(StrEnum):
    """Common nested keys used inside stored problem documents."""

    PROBLEM_ID = "problem_id"
    SCENARIO_ID = "scenario_id"
    PROPOSAL_ID = "proposal_id"
