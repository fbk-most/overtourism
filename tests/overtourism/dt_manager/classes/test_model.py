# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from overtourism.dt_manager.classes.model import ModelEvaluator, ModelOutput


def test_model_output_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelOutput()


def test_model_evaluator_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelEvaluator()
