import typing
from dataclasses import dataclass, field

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.scenario.scenario import Scenario


@dataclass
class SessionState:
    """In-memory working context for drafts, evaluations, and later chats."""

    session_id: str
    problem_id: str
    created: str
    updated: str
    metadata: dict[str, typing.Any] = field(default_factory=dict)
    drafts: dict[str, Scenario] = field(default_factory=dict)
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    active_scenario_id: str | None = None
