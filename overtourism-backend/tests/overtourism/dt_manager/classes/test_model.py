# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from civic_digital_twins.dt_model.simulation.runner import ModelEvaluator, ModelOutput


def test_model_evaluator_and_output_importable_from_cdt() -> None:
    """ModelEvaluator and ModelOutput are directly importable from civic_digital_twins."""
    assert ModelEvaluator is not None
    assert ModelOutput is not None


def test_model_evaluator_is_abstract() -> None:
    """CDT ModelEvaluator requires a model arg and has abstract input_schema."""
    with pytest.raises(TypeError):
        ModelEvaluator()  # type: ignore[call-arg]
