# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

# Re-export CDT's canonical ABCs so that downstream code importing from
# ``dt_manager.classes.model`` continues to work after the CDT 0.9.x upgrade.
from civic_digital_twins.dt_model.simulation.runner import (
    ModelEvaluator,  # noqa: F401
    ModelOutput,  # noqa: F401
)

__all__ = ["ModelEvaluator", "ModelOutput"]
