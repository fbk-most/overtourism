import typing
from dataclasses import dataclass, field

from overtourism.dt_manager.evaluation.evaluation import Evaluation
from overtourism.dt_manager.scenario.scenario import Scenario
from overtourism.dt_manager.utils.dictable import Dictable


@dataclass
class SessionState(Dictable):
    """In-memory working context for scenarios, evaluations, and later chats."""

    session_id: str
    tenant: str
    created: str
    updated: str
    owner_id: str | None = None
    metadata: dict[str, typing.Any] = field(default_factory=dict)
    scenarios: dict[str, Scenario] = field(default_factory=dict)
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    active_scenario_id: str | None = None
