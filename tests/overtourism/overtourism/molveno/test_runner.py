# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario

from overtourism.overtourism.setup import model_evaluator


def test_get_index_diffs_formats_percentage_widgets_on_ui_scale() -> None:
    overrides = model_evaluator._values_to_overrides(
        model_evaluator._model,
        {
            "tourists_parking_percentage": 0.61,
            "tourists_per_vehicle_average": 3.0,
        },
    )
    scenario = CDTScenario(model_evaluator._model, overrides=overrides)

    assert model_evaluator.get_index_diffs(scenario) == {
        "tourists_parking_percentage": "2 -> 61",
        "tourists_per_vehicle_average": "2.5 -> 3",
    }
