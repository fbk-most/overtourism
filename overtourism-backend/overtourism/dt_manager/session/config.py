# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SessionCleanupConfig:
    session_scenario_ttl_seconds: float = 604800
    session_cleanup_interval_seconds: float = 86400

    def __post_init__(self) -> None:
        if not isfinite(self.session_scenario_ttl_seconds) or (
            self.session_scenario_ttl_seconds <= 0
        ):
            raise ValueError("session_scenario_ttl_seconds must be positive")
        if not isfinite(self.session_cleanup_interval_seconds) or (
            self.session_cleanup_interval_seconds <= 0
        ):
            raise ValueError("session_cleanup_interval_seconds must be positive")
