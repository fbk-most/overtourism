# SPDX-License-Identifier: Apache-2.0
"""Layer 3 computation backend for the Fazzon model — see `overtourism/BACKEND_DESIGN.md` §5.

The single evaluation path for the Fazzon model: builds its own seeded
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
from overtourism.layer_3.model.fazzon.fazzon_model import FazzonModel
from overtourism.layer_3.model.fazzon.schema_metadata import SCHEMA_METADATA


class FazzonBackend:
    """Frontend-agnostic computation backend for the Fazzon model.

    Constructor builds the model, the index map, and holds an
    `OvertourismEvaluationConfig` with fixed seeds and sample counts — seeds
    are a compute-quality concern and live here, not in the frontend.
    """

    def __init__(self) -> None:
        model = FazzonModel(inputs=FazzonModel.default_inputs())
        self._model = model
        self._index_map: dict[str, Any] = {idx.name: idx for idx in model.indexes}
        self._parameter_axes = [
            model.inputs.pv_visitors_car,
            model.inputs.pv_visitors_other,
        ]
        # Grid-resolution: structural axis choices, not per-evaluation config.
        self._c_max, self._o_max = 2000, 1000
        self._c_sample, self._o_sample = 100, 100
        self._config = OvertourismEvaluationConfig(
            ensemble_size=8,  # 4 seasons x 2 day_types
            ensemble_seed=0,
            n_samples_per_combo=10,
            sample_seed=1,
            target_presence_samples=2000,
            confidence=0.8,
        )

    def parameter_schema(self) -> list[OvertourismParameterMeta]:
        """Return the ordered, self-describing parameter schema."""
        return list(self._schema.values())

    def schema(self) -> dict[str, Any]:
        """Return Fazzon indexes and placeholder frontend metadata."""
        return {
            "metadata": SCHEMA_METADATA,
            "indexes": self.parameter_schema(),
        }

    @property
    def model(self) -> FazzonModel:
        """The live `FazzonModel` instance.

        Needed by frontends that resolve predefined what-if scenarios
        (`Index`-keyed ``overrides_fn`` callables) against a live model, e.g.
        `fazzon_scenarios.ALL_SCENARIOS`.
        """
        return self._model

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
        """Arrange Fazzon output for the frontend presentation format."""
        return arrange_frontend_data(output)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @functools.cached_property
    def _schema(self) -> dict[str, OvertourismParameterMeta]:
        """Hand-authored parameter metadata; the single source of truth (§3.1)."""
        inp = self._model.inputs
        return {
            inp.i_car_mode_share.name: OvertourismParameterMeta(
                name=inp.i_car_mode_share.name,
                kind="scalar",
                label="Quota modale auto",
                description=(
                    "Frazione di visitatori che arriva in auto. "
                    "Riferimento: 69 % (EETRA 2022). "
                    "Ridurre per simulare tariffazione o shift modale."
                ),
                category="Mobilità",
                default=0.69,
                min_value=0.30,
                max_value=1.00,
                step=0.01,
            ),
            inp.i_shuttle_daily_trips.name: OvertourismParameterMeta(
                name=inp.i_shuttle_daily_trips.name,
                kind="scalar",
                label="Viaggi navetta / giorno",
                description=(
                    "Passaggi totali del veicolo navetta (andata + ritorno). 0 = nessuna navetta.  32 = 2 bus × 8 A/R."
                ),
                unit="corse",
                category="Navetta",
                default=0.0,
                min_value=0.0,
                max_value=96.0,
                step=4.0,
            ),
            inp.cv_season.name: OvertourismParameterMeta(
                name=inp.cv_season.name,
                kind="categorical",
                label="Stagione",
                description=(
                    "Vincola la valutazione a una singola stagione. "
                    "Lasciare su '(tutte)' per la media ponderata stagionale."
                ),
                category="Contesto",
                support=list(inp.cv_season.support),
            ),
            inp.cv_day_type.name: OvertourismParameterMeta(
                name=inp.cv_day_type.name,
                kind="categorical",
                label="Tipo di giorno",
                description="Picco = domeniche di luglio e lun/mar di agosto.  Base = tutti gli altri giorni.",
                category="Contesto",
                support=list(inp.cv_day_type.support),
            ),
            inp.i_c_parking.name: OvertourismParameterMeta(
                name=inp.i_c_parking.name,
                kind="distribution",
                label="Cap parcheggio (auto simultanee)",
                description=(
                    "Range [min, max] del numero massimo di auto in parcheggio simultaneo. "
                    "Riferimento 2025: triangolare moda 200, range [150, 250]."
                ),
                unit="auto",
                category="Capacità",
                default_range=(150.0, 250.0),
                min_value=50.0,
                max_value=500.0,
                step=10.0,
                distribution_family="triang",
                distribution_fixed_params={"c": 0.5},
            ),
            inp.i_c_lakeside.name: OvertourismParameterMeta(
                name=inp.i_c_lakeside.name,
                kind="distribution",
                label="Capacità lago (persone simultanee)",
                description=(
                    "Range [min, max] della soglia di capacità del lungolago. "
                    "ASSUNZIONE — non validata con esperti (Domanda aperta #13)."
                ),
                unit="persone",
                category="Capacità",
                default_range=(400.0, 800.0),
                min_value=100.0,
                max_value=1200.0,
                step=50.0,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
        }

    def _evaluate_scenario(self, scenario: Scenario) -> SustainabilityFieldOutput:
        """Run the seeded field + presence-sample evaluation for `scenario`."""
        model = self._model
        config = self._config
        pv_car, pv_other = model.inputs.pv_visitors_car, model.inputs.pv_visitors_other
        cc = np.linspace(0, self._c_max, self._c_sample + 1)
        oo = np.linspace(0, self._o_max, self._o_sample + 1)

        # Presence samples for the scatter overlay — seeded independently of the field.
        sampling_overrides = {
            idx: (
                [val]
                if isinstance(idx, CategoricalIndex) and isinstance(val, str)
                else val
            )
            for idx, val in scenario.overrides.items()
        }
        sampling_scenario = Scenario(
            model, overrides=sampling_overrides, parameter_axes=[pv_car, pv_other]
        )
        sampling_ensemble = CrossProductEnsemble(
            sampling_scenario,
            max_categorical_size=config.ensemble_size,
            rng=np.random.default_rng(config.sample_seed),
        )
        pv_samples = sample_across(
            sampling_ensemble,
            [pv_car, pv_other],
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
            parameters={pv_car: cc, pv_other: oo},
        )
        field, field_elements, usage_fields, capacity_distributions = (
            compute_sustainability_field(
                model.constraints, result, pv_car, pv_other, scenario=scenario
            )
        )

        return SustainabilityFieldOutput(
            field=field,
            field_elements=field_elements,
            x_values=cc,
            y_values=oo,
            x_axis_name="Visitatori in auto / giorno",
            y_axis_name="Visitatori non-auto / giorno",
            samples_x=list(pv_samples[pv_car]),
            samples_y=list(pv_samples[pv_other]),
            usage_fields=usage_fields,
            capacity_distributions=capacity_distributions,
            confidence=config.confidence,
        )
