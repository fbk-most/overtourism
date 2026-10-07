# SPDX-License-Identifier: Apache-2.0
"""Layer 3 computation backend for the Molveno model — see `overtourism/BACKEND_DESIGN.md` §5.

The single evaluation path for the Molveno model: builds its own seeded
`CrossProductEnsemble`/`Evaluation` and targets
`overtourism.model.common.sustainability_field.SustainabilityFieldOutput`
directly via the shared field-math functions.
"""

from __future__ import annotations

import functools
from typing import Any, ClassVar

import numpy as np
from civic_digital_twins.dt_model import (
    CategoricalIndex,
    CrossProductEnsemble,
    Evaluation,
    Scenario,
    build_scenario,
    sample_across,
)

from src.model.common.sustainability_field import (
    OvertourismEvaluationConfig,
    OvertourismParameterMeta,
    SustainabilityFieldOutput,
    arrange_frontend_data,
    compute_sustainability_field,
)
from src.model.molveno.molveno_model import MolvenoModel


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

    # Subsystem/constraint display names and axis labels — the backend's own
    # minimal, structural presentation metadata, hardcoded here the same way
    # `_schema` hardcodes parameter metadata. `schema()` returns these
    # verbatim
    MAPPER: ClassVar[dict[str, str]] = {
        "parking": "Parcheggi",
        "beach": "Spiaggia",
        "accommodation": "Alberghi",
        "food": "Ristoranti",
    }
    X_AXIS_NAME = "Turisti / giorno"
    Y_AXIS_NAME = "Escursionisti / giorno"
    # TODO: check: are thesepointers really needed?
    X_FIELD = "tourist"
    Y_FIELD = "excursionist"

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
            "metadata": {
                "mapper": self.MAPPER,
                "x_axis_name": self.X_AXIS_NAME,
                "y_axis_name": self.Y_AXIS_NAME,
                "x_field": self.X_FIELD,
                "y_field": self.Y_FIELD,
            },
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

        Exposes the three context variables and the full set of model
        parameters, except the presence variables. Percentages are expressed
        as fractions, matching the model's units.
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
                    "Con tempo 'bad' la ristorazione assorbe una maggiore quota "
                    "di escursionisti."
                ),
                category="Contesto",
                support=list(inp.cv_weather.support),
            ),
            inp.i_c_parking.name: OvertourismParameterMeta(
                name=inp.i_c_parking.name,
                kind="distribution",
                label="Numero di parcheggi disponibili",
                description=(
                    "Numero di posti auto disponibili a Molveno. "
                    "Range [min, max]; riferimento: uniform[350, 450]."
                ),
                category="Parcheggi",
                default_range=(350.0, 450.0),
                min_value=0.0,
                max_value=1000.0,
                step=10.0,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
            inp.i_u_tourists_parking.name: OvertourismParameterMeta(
                name=inp.i_u_tourists_parking.name,
                kind="scalar",
                label="Percentuale di turisti che usano i parcheggi",
                description=("Frazione di turisti che usano i parcheggi."),
                category="Parcheggi",
                default=0.02,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_u_excursionists_parking.name: OvertourismParameterMeta(
                name=inp.i_u_excursionists_parking.name,
                kind="scalar",
                label="Percentuale di escursionisti che usano i parcheggi",
                description=("Frazione di escursionisti che usano i parcheggi."),
                category="Parcheggi",
                default=0.80,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_xa_tourists_per_vehicle.name: OvertourismParameterMeta(
                name=inp.i_xa_tourists_per_vehicle.name,
                kind="scalar",
                label="Numero medio di turisti per veicolo",
                description=(
                    "Occupazione media (numero medio di persone) nei veicoli "
                    "utilizzati dai turisti."
                ),
                category="Parcheggi",
                default=2.5,
                min_value=0.1,
                max_value=5.0,
                step=0.1,
            ),
            inp.i_xa_excursionists_per_vehicle.name: OvertourismParameterMeta(
                name=inp.i_xa_excursionists_per_vehicle.name,
                kind="scalar",
                label="Numero medio di escursionisti per veicolo",
                description=(
                    "Occupazione media (numero medio di persone) nei veicoli "
                    "utilizzati dagli escursionisti."
                ),
                category="Parcheggi",
                default=2.5,
                min_value=0.1,
                max_value=5.0,
                step=0.1,
            ),
            inp.i_xo_tourists_parking.name: OvertourismParameterMeta(
                name=inp.i_xo_tourists_parking.name,
                kind="scalar",
                label="Ricambi giornalieri per posto auto (turisti)",
                description=(
                    "Numero di veicoli di turisti che possono occupare lo stesso "
                    "posto auto nell'arco della giornata."
                ),
                category="Parcheggi",
                default=1.05,
                min_value=1.0,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_xo_excursionists_parking.name: OvertourismParameterMeta(
                name=inp.i_xo_excursionists_parking.name,
                kind="scalar",
                label="Ricambi giornalieri per posto auto (escursionisti)",
                description=(
                    "Numero di veicoli di escursionisti che possono occupare lo stesso "
                    "posto auto nell'arco della giornata."
                ),
                category="Parcheggi",
                default=3.5,
                min_value=1.0,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_c_beach.name: OvertourismParameterMeta(
                name=inp.i_c_beach.name,
                kind="distribution",
                label="Numero di posti disponibili in spiaggia",
                description=(
                    "Numero massimo di presenze nella spiaggia di Molveno che garantiscono "
                    "un distanziamento adeguato fra le persone. "
                    "Range [min, max]; riferimento: uniform[6000, 7000]."
                ),
                category="Spiaggia",
                default_range=(6000.0, 7000.0),
                min_value=0.0,
                max_value=10000.0,
                step=100.0,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
            inp.i_u_tourists_beach.name: OvertourismParameterMeta(
                name=inp.i_u_tourists_beach.name,
                kind="scalar",
                label="Percentuale di turisti che usano la spiaggia",
                description=("Frazione di turisti che usano la spiaggia."),
                category="Spiaggia",
                default=0.50,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_u_excursionists_beach.name: OvertourismParameterMeta(
                name=inp.i_u_excursionists_beach.name,
                kind="scalar",
                label="Percentuale di escursionisti che usano la spiaggia",
                description=("Frazione di escursionisti che usano la spiaggia."),
                category="Spiaggia",
                default=0.80,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_xo_tourists_beach.name: OvertourismParameterMeta(
                name=inp.i_xo_tourists_beach.name,
                kind="distribution",
                label="Ricambi giornalieri per posto in spiaggia (turisti)",
                description=(
                    "Numero di turisti che possono occupare lo stesso posto in spiaggia "
                    "nell'arco della giornata. Range [min, max]; riferimento: uniform[1, 3]."
                ),
                category="Spiaggia",
                default_range=(1.0, 3.0),
                min_value=1.0,
                max_value=4.0,
                step=0.05,
                distribution_family="uniform",
                distribution_fixed_params={},
            ),
            inp.i_xo_excursionists_beach.name: OvertourismParameterMeta(
                name=inp.i_xo_excursionists_beach.name,
                kind="scalar",
                label="Ricambi giornalieri per posto in spiaggia (escursionisti)",
                description=(
                    "Numero di escursionisti che possono occupare lo stesso posto in "
                    "spiaggia nell'arco della giornata."
                ),
                category="Spiaggia",
                default=1.05,
                min_value=1.0,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_c_accommodation.name: OvertourismParameterMeta(
                name=inp.i_c_accommodation.name,
                kind="distribution",
                label="Posti letto disponibili",
                description=(
                    "Totale posti letto nelle strutture ricettive alberghiere e "
                    "extralberghiere a Molveno. Distribuzione lognormale (s = 0.125) "
                    "con loc = min e scale = max - min; riferimento: loc 0, scale 5000."
                ),
                category="Alberghi",
                default_range=(0.0, 5000.0),
                min_value=0.0,
                max_value=10000.0,
                step=100.0,
                distribution_family="lognorm",
                distribution_fixed_params={"s": 0.125},
            ),
            inp.i_u_tourists_accommodation.name: OvertourismParameterMeta(
                name=inp.i_u_tourists_accommodation.name,
                kind="scalar",
                label="Percentuale di turisti che alloggiano in strutture ricettive",
                description=(
                    "Frazione di turisti che alloggiano in strutture ricettive alberghiere "
                    "o extralberghiere a Molveno."
                ),
                category="Alberghi",
                default=0.90,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_xa_tourists_accommodation.name: OvertourismParameterMeta(
                name=inp.i_xa_tourists_accommodation.name,
                kind="scalar",
                label="Fattore massimo di allocazione dei posti letto",
                description=(
                    "Fattore di allocazione che rappresenta la frazione di posti letto "
                    "occupati nel caso di alberghi pieni (tenendo conto ad es. di camere "
                    "doppie uso singola)."
                ),
                category="Alberghi",
                default=0.85,
                min_value=0.5,
                max_value=1.25,
                step=0.05,
            ),
            inp.i_c_food.name: OvertourismParameterMeta(
                name=inp.i_c_food.name,
                kind="distribution",
                label="Posti a sedere nei ristoranti",
                description=(
                    "Totale posti a sedere nella ristorazione commerciale a Molveno. "
                    "Range [min, max]; riferimento: triang moda 2800, range [2400, 3200]."
                ),
                category="Ristoranti",
                default_range=(2400.0, 3200.0),
                min_value=0.0,
                max_value=6000.0,
                step=100.0,
                distribution_family="triang",
                distribution_fixed_params={"c": 0.5},
            ),
            inp.i_u_tourists_food.name: OvertourismParameterMeta(
                name=inp.i_u_tourists_food.name,
                kind="scalar",
                label="Percentuale di turisti che usano i ristoranti",
                description=("Frazione di turisti che usano i ristoranti."),
                category="Ristoranti",
                default=0.20,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_u_excursionists_food_bad_weather.name: OvertourismParameterMeta(
                name=inp.i_u_excursionists_food_bad_weather.name,
                kind="scalar",
                label="Percentuale di escursionisti che usano i ristoranti (maltempo)",
                description=(
                    "Frazione di escursionisti che usano i ristoranti con meteo 'bad'."
                ),
                category="Ristoranti",
                default=0.80,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_u_excursionists_food_good_unsettled_weather.name: OvertourismParameterMeta(
                name=inp.i_u_excursionists_food_good_unsettled_weather.name,
                kind="scalar",
                label="Percentuale di escursionisti che usano i ristoranti (tempo bello / variabile)",
                description=(
                    "Frazione di escursionisti che usano i ristoranti "
                    "con meteo 'good' o 'unsettled'."
                ),
                category="Ristoranti",
                default=0.40,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),
            inp.i_xa_visitors_food.name: OvertourismParameterMeta(
                name=inp.i_xa_visitors_food.name,
                kind="scalar",
                label="Fattore massimo di allocazione dei posti a sedere nei ristoranti",
                description=(
                    "Fattore di allocazione che rappresenta la frazione di posti a sedere "
                    "occupati nel caso di ristoranti pieni (tenendo conto ad es. di tavoli "
                    "non completi)."
                ),
                category="Ristoranti",
                default=0.90,
                min_value=0.5,
                max_value=1.5,
                step=0.05,
            ),
            inp.i_xo_visitors_food.name: OvertourismParameterMeta(
                name=inp.i_xo_visitors_food.name,
                kind="scalar",
                label="Tasso di rotazione dei tavoli",
                description=(
                    "Numero di volte in cui un tavolo viene occupato nell'arco di un servizio."
                ),
                category="Ristoranti",
                default=2.0,
                min_value=0.5,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_p_tourists_reduction_factor.name: OvertourismParameterMeta(
                name=inp.i_p_tourists_reduction_factor.name,
                kind="scalar",
                label="Fattore di variazione di presenze turistiche",
                description=(
                    "Aumenta (> 1) o diminuisce (< 1) la presenza stimata di "
                    "turisti rispetto al valore storico."
                ),
                category="Flussi",
                default=1.0,
                min_value=0.05,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_p_excursionists_reduction_factor.name: OvertourismParameterMeta(
                name=inp.i_p_excursionists_reduction_factor.name,
                kind="scalar",
                label="Fattore di variazione di presenze escursionistiche",
                description=(
                    "Aumenta (> 1) o diminuisce (< 1) la presenza stimata di "
                    "escursionisti rispetto al valore storico."
                ),
                category="Flussi",
                default=1.0,
                min_value=0.05,
                max_value=4.0,
                step=0.05,
            ),
            inp.i_p_tourists_saturation_level.name: OvertourismParameterMeta(
                name=inp.i_p_tourists_saturation_level.name,
                kind="scalar",
                label="Soglia di saturazione massima turisti",
                description=(
                    "Livello massimo che può raggiungere la presenza di "
                    "turisti a Molveno durante una giornata."
                ),
                category="Flussi",
                default=10000.0,
                min_value=1000.0,
                max_value=20000.0,
                step=100.0,
            ),
            inp.i_p_excursionists_saturation_level.name: OvertourismParameterMeta(
                name=inp.i_p_excursionists_saturation_level.name,
                kind="scalar",
                label="Soglia di saturazione massima escursionisti",
                description=(
                    "Livello massimo che può raggiungere la presenza di "
                    "escursionisti a Molveno durante una giornata."
                ),
                category="Flussi",
                default=10000.0,
                min_value=1000.0,
                max_value=20000.0,
                step=100.0,
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
            samples_x=samples_x,
            samples_y=samples_y,
            usage_fields=usage_fields,
            capacity_distributions=capacity_distributions,
            confidence=config.confidence,
        )
