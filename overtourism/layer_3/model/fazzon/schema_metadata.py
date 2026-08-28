# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

RISK_COLOR_SCALE: list[tuple[float, str]] = [
	(0.0, "rgb(5, 102, 8)"),
	(0.05, "rgb(100, 180, 90)"),
	(0.20, "rgb(180, 230, 170)"),
	(0.40, "rgb(230, 250, 225)"),
	(0.50, "yellow"),
	(0.60, "rgb(255, 242, 242)"),
	(0.80, "rgb(242, 204, 204)"),
	(0.95, "rgb(204, 76, 76)"),
	(1.0, "rgb(180, 4, 38)"),
]

SUBSYSTEM_MAPPER: dict[str, str] = {
	"default": "Tutti",
	"parking": "Parcheggi",
	"road": "Viabilità",
	"food": "Ristorazione",
	"lakeside": "Lungolago",
}

KPI_MAPPER: dict[str, str] = {
	"title": "Indici",
	"area": "Area Totale",
	"overtourism_level": "Giorni di criticità complessiva",
	"constraint level parking": "Giorni di criticità Parcheggi",
	"constraint level road": "Giorni di criticità Viabilità",
	"constraint level food": "Giorni di criticità Ristorazione",
	"constraint level lakeside": "Giorni di criticità Lungolago",
	"critical constraint": "Vincolo Critico",
}

PLOT_MAPPER: dict[str, dict] = {
	"monodimensional": {
		"x": {"label": "Giorni (ordinati per utilizzo)"},
		"y": {"label": "Livello di utilizzo della destinazione", "field": "usage"},
	},
	"bidimensional": {
		"x": {"label": "Visitatori in auto / giorno", "field": "visitors_car"},
		"y": {"label": "Visitatori non-auto / giorno", "field": "visitors_other"},
	},
}

SCHEMA_METADATA: dict[str, object] = {
	"mapper": SUBSYSTEM_MAPPER,
	"color_map": RISK_COLOR_SCALE,
	"kpi_mapper": KPI_MAPPER,
	"plot_mapper": PLOT_MAPPER,
}
