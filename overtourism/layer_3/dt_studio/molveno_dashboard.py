# SPDX-License-Identifier: Apache-2.0
"""Streamlit dashboard entry point for the Molveno overtourism model.

Dev/test tooling only — not part of the application backend. Run with::

    uv run streamlit run overtourism/dt_studio/molveno_dashboard.py
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from overtourism.layer_3.dt_studio.dashboard.adapter import (
    OvertourismAdapter,
    PlotData,
    ScenarioDef,
)
from overtourism.layer_3.dt_studio.dashboard.app import run_dashboard
from overtourism.layer_3.model.common.sustainability_field import (
    OvertourismParameterMeta,
)
from overtourism.layer_3.model.molveno.molveno_backend import MolvenoBackend

# ---------------------------------------------------------------------------
# Predefined scenarios
# ---------------------------------------------------------------------------

_MOLVENO_SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "typical",
        "label": "Giorno tipico (media stagionale)",
        "category": "Riferimento",
        "description": (
            "Nessun vincolo contestuale: media ponderata su tutti i giorni della settimana, "
            "tutte le stagioni e tutte le condizioni meteo secondo le frequenze storiche."
        ),
        "overrides": {},
    },
    {
        "key": "peak_summer_saturday",
        "label": "Sabato picco estivo (buon tempo)",
        "category": "Scenari estremi",
        "description": (
            "Condizioni di massima affluenza: stagione 'very high', sabato, meteo buono. "
            "Tipico di luglio–agosto con sole."
        ),
        "overrides": {"season": "very high", "weekday": "saturday", "weather": "good"},
    },
    {
        "key": "rainy_day",
        "label": "Giornata di pioggia (estate)",
        "category": "Scenari estremi",
        "description": (
            "Stagione 'very high', sabato, meteo 'bad'. La spiaggia si svuota e la ristorazione è satura."
        ),
        "overrides": {"season": "very high", "weekday": "saturday", "weather": "bad"},
    },
    {
        "key": "low_season_weekday",
        "label": "Giorno feriale bassa stagione",
        "category": "Riferimento",
        "description": "Stagione 'low', lunedì, meteo buono: condizioni di bassa pressione.",
        "overrides": {"season": "low", "weekday": "monday", "weather": "good"},
    },
]


# ---------------------------------------------------------------------------
# MolvenoAdapter
# ---------------------------------------------------------------------------


class MolvenoAdapter(OvertourismAdapter):
    """Adapter bridging :class:`~molveno_backend.MolvenoBackend` to the generic dashboard."""

    def __init__(self) -> None:
        self._backend = MolvenoBackend()

    @property
    def title(self) -> str:
        """Dashboard page title."""
        return "Overtourism Digital Twin — Molveno (Lago di Molveno)"

    def parameter_specs(self) -> list[OvertourismParameterMeta]:
        """Return the backend's parameter schema, in schema-declaration order."""
        return self._backend.parameter_schema()

    def predefined_scenarios(self) -> list[ScenarioDef]:
        """Build ScenarioDef objects from the Molveno built-in scenario catalogue."""
        specs = self.parameter_specs()
        spec_map = {s.name: s for s in specs}

        scenario_defs: list[ScenarioDef] = []
        for s in _MOLVENO_SCENARIOS:
            # Start from spec defaults
            params: dict[str, Any] = {}
            for spec in specs:
                if spec.kind == "distribution" and spec.default_range is not None:
                    params[spec.name] = spec.default_range
                # categoricals: absent = "(tutte)" — averaged over all values

            # Apply the scenario's CV overrides by matching index name suffixes
            for cv_key, cv_val in s["overrides"].items():
                # cv_key is a short label ("season", "weekday", "weather")
                matching = next(
                    (name for name in spec_map if cv_key in name),
                    None,
                )
                if matching:
                    params[matching] = cv_val

            scenario_defs.append(
                ScenarioDef(
                    key=s["key"],
                    label=s["label"],
                    category=s["category"],
                    description=s["description"],
                    params=params,
                )
            )
        return scenario_defs

    def run(self, param_overrides: dict[str, Any]) -> PlotData:
        """Evaluate the Molveno model and return visualisation-ready data."""
        output = self._backend.evaluate(param_overrides)

        return PlotData(
            field=output.field,
            field_elements=output.field_elements,
            x_values=output.x_values,
            y_values=output.y_values,
            x_label=output.x_axis_name,
            y_label=output.y_axis_name,
            samples_x=output.samples_x,
            samples_y=output.samples_y,
            sustainability_index=output.sustainability_index,
            sustainability_by_constraint=output.sustainability_by_constraint,
            modal_lines=output.modal_lines,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@st.cache_resource
def _get_adapter() -> MolvenoAdapter:
    return MolvenoAdapter()


run_dashboard(_get_adapter())
