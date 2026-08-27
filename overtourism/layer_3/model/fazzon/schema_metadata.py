# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

# Placeholder until Fazzon's frontend metadata is defined.
RISK_COLOR_SCALE: list[tuple[float, str]] = []
SUBSYSTEM_MAPPER: dict[str, str] = {}
KPI_MAPPER: dict[str, str] = {}
PLOT_MAPPER: dict[str, dict] = {
	"monodimensional": {},
	"bidimensional": {},
}

SCHEMA_METADATA: dict[str, object] = {
	"mapper": SUBSYSTEM_MAPPER,
	"color_map": RISK_COLOR_SCALE,
	"kpi_mapper": KPI_MAPPER,
	"plot_mapper": PLOT_MAPPER,
}
