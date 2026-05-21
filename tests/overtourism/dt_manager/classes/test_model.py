# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from overtourism.dt_manager.classes.model import ModelEvaluator, ModelOutput


def test_model_output_can_be_used_as_base_for_dataclasses() -> None:
    """CDT ModelOutput is a concrete ABC (not abstract-instantiable directly)."""
    # The CDT ModelOutput can be instantiated directly (no abstract methods),
    # but _serialize/_deserialize raise NotImplementedError for non-dataclasses.
    # Subclasses are the intended usage.
    from civic_digital_twins.dt_model.simulation.runner import (
        ModelOutput as CDTModelOutput,
    )

    assert ModelOutput is CDTModelOutput


def test_model_evaluator_is_abstract() -> None:
    """CDT ModelEvaluator requires a model arg and has abstract input_schema."""
    with pytest.raises(TypeError):
        ModelEvaluator()  # type: ignore[call-arg]
