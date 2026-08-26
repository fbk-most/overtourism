# SPDX-License-Identifier: Apache-2.0
"""Layer 3 computation backend for the Molveno model — see `overtourism/BACKEND_DESIGN.md` §5.

The single evaluation path for the Molveno model: builds its own seeded
`CrossProductEnsemble`/`Evaluation` and targets
`overtourism.model.common.sustainability_field.SustainabilityFieldOutput`
directly via the shared field-math functions.
"""

from __future__ import annotations

import functools
from typing import Any

import numpy as np
from civic_digital_twins.dt_model import (
    CategoricalIndex,
    CrossProductEnsemble,
    Evaluation,
    Scenario,
    sample_across,
)

from overtourism.layer_3.cdt_ext.runner_ext import build_scenario
from overtourism.layer_3.model.common.sustainability_field import (
    OvertourismEvaluationConfig,
    OvertourismParameterMeta,
    SustainabilityFieldOutput,
    arrange_frontend_data,
    compute_sustainability_field,
)
from overtourism.layer_3.model.molveno.molveno_model import MolvenoModel
from overtourism.layer_3.model.molveno.schema_metadata import (
    RISK_COLOR_SCALE,
    SUBSYSTEM_MAPPER,
    KPI_MAPPER,
)


def _presence_transformation(
    presence: float,
    reduction_factor: float,
    saturation_level: float,
    sharpness: int = 3,
) -> float:
    """Apply the presence saturation transformation used for scatter-plot samples.

    Molveno-specific (unlike the field math in `overtourism.model.common`): it
    depends on `i_p_*_reduction_factor`/`i_p_*_saturation_level`, parameters
    that only exist on `MolvenoModel`.
    """
    tmp = presence * reduction_factor
    return (
        tmp
        * saturation_level
        / ((tmp**sharpness + saturation_level**sharpness) ** (1 / sharpness))
    )


class MolvenoBackend:
    """Frontend-agnostic computation backend for the Molveno model.

    Constructor builds the model, the index map, and holds an
    `OvertourismEvaluationConfig` with fixed seeds and sample counts — seeds
    are a compute-quality concern and live here, not in the frontend.
    """

    def __init__(self) -> None:
        model = MolvenoModel(inputs=MolvenoModel.default_inputs())
        self._model = model
        self._index_map: dict[str, Any] = {idx.name: idx for idx in model.indexes}
        self._parameter_axes = [model.inputs.pv_tourists, model.inputs.pv_excursionists]
        # Grid-resolution: structural axis choices, not per-evaluation config.
        self._t_max, self._e_max = 10000, 10000
        self._t_sample, self._e_sample = 100, 100
        self._config = OvertourismEvaluationConfig(
            ensemble_size=84,  # 7 weekdays x 4 seasons x 3 weather
            ensemble_seed=0,
            n_samples_per_combo=1,
            sample_seed=1,
            target_presence_samples=2000,
            confidence=0.8,
        )

    @property
    def model(self) -> MolvenoModel:
        """The live `MolvenoModel` instance.

        Needed by frontends that resolve predefined what-if scenarios against
        a live model.
        """
        return self._model

    def parameter_schema(self) -> list[OvertourismParameterMeta]:
        """Return the ordered, self-describing parameter schema."""
        return list(self._schema.values())

    def schema(self) -> dict[str, Any]:
        """Return Molveno indexes and frontend presentation metadata."""
        return {
            "metadata": {"mapper": SUBSYSTEM_MAPPER, "color_map": RISK_COLOR_SCALE, "kpi_mapper": KPI_MAPPER},
            "indexes": self.parameter_schema(),
        }

    def evaluate(self, param_overrides: dict[str, Any]) -> SustainabilityFieldOutput:
        """Evaluate the model under the given string-keyed parameter overrides."""
        scenario = build_scenario(
            self._model,
            param_overrides,
            self._index_map,
            self._schema,
            self._parameter_axes,
        )
        return self._evaluate_scenario(scenario)

    def arrange_data(self, output: SustainabilityFieldOutput) -> dict[str, Any]:
        """Arrange Molveno output for the frontend presentation format."""
        return arrange_frontend_data(output)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @functools.cached_property
    def _schema(self) -> dict[str, OvertourismParameterMeta]:
        """Hand-authored parameter metadata; the single source of truth (§3.1).

        Curated subset matching the current dashboard: exposes the three
        context variables and the parking/beach/food capacities, but not
        `i_c_accommodation` or `i_xo_tourists_beach` (both distribution-backed
        on the model but not surfaced as sliders today).
        """
        inp = self._model.inputs
        return {
            inp.cv_weekday.name: OvertourismParameterMeta(
                name=inp.cv_weekday.name,
                kind="categorical",
                label="Giorno della settimana",
                description=(
                    "Filtra la valutazione a un singolo giorno della settimana. "
                    "Il sabato registra la maggiore presenza di escursionisti."
                ),
                category="Contesto",
                support=list(inp.cv_weekday.support),
            ),
            inp.cv_season.name: OvertourismParameterMeta(
                name=inp.cv_season.name,
                kind="categorical",
                label="Stagione",
                description=(
                    "Cluster stagionale: 'very high' = picco estivo (≈20% dei giorni), "
                    "'high' ≈ 26%, 'mid' ≈ 29%, 'low' ≈ 24%."
                ),
                category="Contesto",
                support=list(inp.cv_season.support),
            ),
            inp.cv_weather.name: OvertourismParameterMeta(
                name=inp.cv_weather.name,
                kind="categorical",
                label="Meteo",
                description=(
                    "Con tempo 'bad' la quota di escursionisti al lago cala drasticamente; "
                    "la ristorazione assorbe una maggiore quota di visitatori."
                ),
                category="Contesto",
                support=list(inp.cv_weather.support),
            ),
            inp.i_c_parking.name: OvertourismParameterMeta(
                name=inp.i_c_parking.name,
                kind="distribution",
                label="Capacità parcheggio (auto)",
                description=(
                    "Range [min, max] della capacità del parcheggio. Valore di riferimento: uniform[350, 450] auto."
                ),
                unit="auto",
                category="Capacità",
                default_range=(350.0, 450.0),
                min_value=100.0,
                max_value=800.0,
                step=10.0,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
            inp.i_c_beach.name: OvertourismParameterMeta(
                name=inp.i_c_beach.name,
                kind="distribution",
                label="Capacità spiaggia (persone)",
                description=(
                    "Range [min, max] della capacità della spiaggia. "
                    "Valore di riferimento: uniform[6000, 7000] persone."
                ),
                unit="persone",
                category="Capacità",
                default_range=(6000.0, 7000.0),
                min_value=3000.0,
                max_value=12000.0,
                step=250.0,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
            inp.i_c_food.name: OvertourismParameterMeta(
                name=inp.i_c_food.name,
                kind="distribution",
                label="Capacità ristorazione (coperti)",
                description=(
                    "Range [min, max] della capacità di ristorazione. "
                    "Valore di riferimento: triang moda 3500, range [3000, 4000] coperti."
                ),
                unit="coperti",
                category="Capacità",
                default_range=(3000.0, 4000.0),
                min_value=1000.0,
                max_value=6000.0,
                step=100.0,
                distribution_family="triang",
                distribution_fixed_params={"c": 0.5},
            ),
        }

    def _evaluate_scenario(self, scenario: Scenario) -> SustainabilityFieldOutput:
        """Run the seeded field + presence-sample evaluation for `scenario`."""
        model = self._model
        config = self._config
        pv_t, pv_e = model.inputs.pv_tourists, model.inputs.pv_excursionists
        tt = np.linspace(0, self._t_max, self._t_sample + 1)
        ee = np.linspace(0, self._e_max, self._e_sample + 1)

        # Raw presence samples — seeded independently of the field. Transformed
        # below (after the field result is available) via _presence_transformation.
        sampling_overrides = {
            idx: (
                [val]
                if isinstance(idx, CategoricalIndex) and isinstance(val, str)
                else val
            )
            for idx, val in scenario.overrides.items()
        }
        sampling_scenario = Scenario(
            model, overrides=sampling_overrides, parameter_axes=[pv_t, pv_e]
        )
        sampling_ensemble = CrossProductEnsemble(
            sampling_scenario,
            max_categorical_size=config.ensemble_size,
            rng=np.random.default_rng(config.sample_seed),
        )
        pv_samples = sample_across(
            sampling_ensemble,
            [pv_t, pv_e],
            total=config.target_presence_samples,
            rng=np.random.default_rng(config.sample_seed),
        )

        # Field ensemble — seeded, n_samples_per_combo capacity-distribution replicates
        # per categorical combo. `scenario` already carries parameter_axes (set by
        # build_scenario), so it's used as-is — no internal rebuild.
        field_ensemble = CrossProductEnsemble(
            scenario,
            max_categorical_size=config.ensemble_size,
            n_samples_per_combo=config.n_samples_per_combo,
            rng=np.random.default_rng(config.ensemble_seed),
        )
        result = Evaluation(scenario).evaluate(
            ensemble=field_ensemble,
            parameters={pv_t: tt, pv_e: ee},
        )
        field, field_elements, usage_fields, capacity_distributions = (
            compute_sustainability_field(
                model.constraints, result, pv_t, pv_e, scenario=scenario
            )
        )

        # Presence-saturation transform: reduction/saturation factors are
        # derived indexes, read from the evaluated result (mean over the ensemble).
        rf_t = float(np.mean(result[model.inputs.i_p_tourists_reduction_factor]))
        sl_t = float(np.mean(result[model.inputs.i_p_tourists_saturation_level]))
        rf_e = float(np.mean(result[model.inputs.i_p_excursionists_reduction_factor]))
        sl_e = float(np.mean(result[model.inputs.i_p_excursionists_saturation_level]))
        samples_x = [_presence_transformation(s, rf_t, sl_t) for s in pv_samples[pv_t]]
        samples_y = [_presence_transformation(s, rf_e, sl_e) for s in pv_samples[pv_e]]

        return SustainabilityFieldOutput(
            field=field,
            field_elements=field_elements,
            x_values=tt,
            y_values=ee,
            x_axis_name="Turisti / giorno",
            y_axis_name="Escursionisti / giorno",
            samples_x=samples_x,
            samples_y=samples_y,
            usage_fields=usage_fields,
            capacity_distributions=capacity_distributions,
            confidence=config.confidence,
        )
