from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from overtourism.overtourism.backend_extension.api.models.indicator import Indicator
from overtourism.overtourism.backend_extension.api.models.trenitno_phenomena import (
    FlowPhenomenon,
    PresencesPhenomenon,
    BedsPhenomenon,
)

# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------
data_dir = (
    Path(__file__).resolve().parents[4] / "overtourism" / "database" / "index_data_v2"
)  # TODO: replace this with dataloader

MAP_SHAPEFILE = data_dir / "Com01012026_g" / "Com01012026_g_WGS84.shp"
MAP_IDS = data_dir / "cities_gdf_base_columns.geojson"
POPULATION_SOURCE = data_dir / "phen_popolazione.parquet"
STRUCTURES_SOURCE = data_dir / "phen_strutture.parquet"
PRESENCES_SOURCE = data_dir / "phen_presenze.parquet"
FLOWS_SOURCE = data_dir / "phen_flussi.parquet"
FLOWS_SOURCE_TEMP_2023 = data_dir / "phen_flussi_temp_2023.parquet"
MACRO_AREAS_FILE = data_dir / "map_comuni_into_apt.json"
CODICI_COMUNI_FILE = data_dir / "mapping_comuni_ISTAT.json"
INCLUDE_TEMP_REGISTRY = False

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY_TEMP: dict[str, Callable[[], Indicator]] = {
    "pressione-turistica": lambda: TouristicPressureIndicator(
        STRUCTURES_SOURCE, PRESENCES_SOURCE
    ),
    # "indice-stagionalita": lambda: SeasonalityIndicator(PRESENCES_SOURCE),
    # "indice-affollamento": lambda: CrowdingIndicator(
    #     STRUCTURES_SOURCE, POPULATION_SOURCE, PRESENCES_SOURCE, FLOWS_SOURCE_TEMP_2023
    # ),
    "ratio-flussi-in-turisti": lambda: RatioFlowsIndicator(FLOWS_SOURCE),
    "ratio-flussi-in-escursionisti": lambda: RatioFlowsIndicator(
        FLOWS_SOURCE, flows_col="FLOWS_IN_VISITORS"
    ),
    "ratio-flussi-out-escursionisti": lambda: RatioFlowsIndicator(
        FLOWS_SOURCE, flows_col="FLOWS_OUT_VISITORS", flows_col_tot="FLOWS_OUT"
    ),
    "ratio-flussi-out-tourists": lambda: RatioFlowsIndicator(
        FLOWS_SOURCE, flows_col="FLOWS_OUT_TOURISTS", flows_col_tot="FLOWS_OUT"
    ),
    "flows-in-escursionisti": lambda: FlowsIndicatorLevel(
        FLOWS_SOURCE, col="LEVEL_IN_VISITORS", flow_col="FLOWS_IN_VISITORS"
    ),
    "flows-in-turisti": lambda: FlowsIndicatorLevel(
        FLOWS_SOURCE, col="LEVEL_IN_TOURISTS", flow_col="FLOWS_IN_TOURISTS"
    ),
    "flows-out-escursionisti": lambda: FlowsIndicatorLevel(
        FLOWS_SOURCE, col="LEVEL_OUT_VISITORS", flow_col="FLOWS_OUT_VISITORS"
    ),
    "flows-out-turisti": lambda: FlowsIndicatorLevel(
        FLOWS_SOURCE, col="LEVEL_OUT_TOURISTS", flow_col="FLOWS_OUT_TOURISTS"
    ),
}

# ---------------------------------------------------------------------------
# Concrete indicators
# ---------------------------------------------------------------------------


class TouristicPressureIndicator(Indicator):
    """Presences over number of available places"""

    # TODO: inserire una misura anche per gli escursionisti e "mediare"

    name = "Indice di pressione turistica"
    type = INDICATORS_TYPES[0]
    description = "L'indice di pressione turistica definisce il <strong>rapporto</strong> fra i <strong>turisti presenti</strong> e i <strong>posti letto disponibili negli esercizi ricettivi</strong>. L'indice è una misura della capacità di carico di una località."
    index_value_unit_description = "Turisti / posti letto"

    def __init__(self, source_file1, source_file2):
        super().__init__(
            phenomena=[
                BedsPhenomenon(source_file1),
                PresencesPhenomenon(
                    source_file2,
                    col="presenze_alb",
                    name="presenze_alb",
                ),
                PresencesPhenomenon(
                    source_file2,
                    col="presenze_xalb",
                    name="presenze_xalb",
                ),
            ],
            combinator=self.compute_touristic_pressure,
        )

    def compute_touristic_pressure(
        self,
        df: pd.DataFrame,
        **extra,
    ) -> pd.Series:
        return (df["presenze_alb"] + df["presenze_xalb"]) / df["beds"]


class RatioFlowsIndicator(Indicator):
    """Calculates the flows indicator as the ratio between tourist/excursionist flows and total flows."""

    def __init__(
        self, source_file, flows_col="FLOWS_IN_TOURISTS", flows_col_tot="FLOWS_IN"
    ):
        phen_name = flows_col.lower()
        phen_name_tot = f"{phen_name}_tot"
        self.name = (
            f"Rapporto di flussi {phen_name.removeprefix('flows_').replace('_', ' ')}"
        )
        super().__init__(
            phenomena=[
                FlowPhenomenon(
                    source_file,
                    col=flows_col,
                    municipality_id_col="ID_COMUNE",
                    name=phen_name,
                ),
                FlowPhenomenon(
                    source_file,
                    col=flows_col_tot,
                    municipality_id_col="ID_COMUNE",
                    name=phen_name_tot,
                ),
            ],
            combinator=self.divide(phen_name, phen_name_tot),
        )


class FlowsIndicatorLevel(Indicator):
    """
    Calculates hotspot level, using 10 - val scale
    """

    def __init__(self, source_file, col="LEVEL_IN", flow_col="FLOWS_IN"):
        self.col = col
        self.name = (
            f"Livello flussi{col.removeprefix('LEVEL').replace('_', ' ').lower()}"
        )
        super().__init__(
            phenomena=[
                FlowPhenomenon(
                    source_file,
                    col=col,
                    municipality_id_col="ID_COMUNE",
                    name=col,
                ),
                FlowPhenomenon(
                    source_file,
                    col=flow_col,
                    municipality_id_col="ID_COMUNE",
                    name="flow_value",
                ),
            ],
            combinator=self.compute_hotspot_level,
        )

    def compute_hotspot_level(self, df: pd.DataFrame, **extra) -> pd.Series:
        return pd.Series(np.where(df[self.col] == -1, 0, 10 - df[self.col]))


# class SeasonalityIndicator(Indicator):
#     """Sum of arrivals in a reference sub-period over total arrivals."""

#     name = "Indice di stagionalità delle presenze"
#     description = "L'indice di stagionalità definisce il <strong>rapporto</strong> fra le <strong>presenze di turisti ed escursionisti durante tra due periodi</strong> (es: anno completo ed alta stagione). L'indice è calcolato partendo dai dati Vodafone relativi alle presenze di turisti ed escursionisti."
#     availableForVariation = False
#     extraFields = ["seasonality"]
#     internal_only = True

#     def __init__(self, source_file):
#         self._phenom = PresencesPhenomenon(source_file, col="presenze_vodafone")
#         super().__init__(
#             phenomena=[self._phenom],
#             combinator=self.reference_period_over_total,
#         )

#     def reference_period_over_total(
#         self,
#         df: pd.DataFrame,
#         filtered_data: dict[str, pd.DataFrame],
#         start_date=None,
#         end_date=None,
#         seasonality: str = "high",
#         **extra,
#     ) -> pd.Series:
#         phenom = self._phenom
#         raw = filtered_data[phenom.name]  # already daily × comune panel slice

#         MONTHLY_PERIODS = {
#             "high": [7, 8],
#             "shoulder": [4, 5, 6, 9, 10],
#         }

#         if seasonality in MONTHLY_PERIODS:
#             months = MONTHLY_PERIODS[seasonality]
#             sub = raw[raw["DATA"].dt.month.isin(months)]
#         elif seasonality == "weekend":
#             all_days = pd.date_range(start=start_date, end=end_date)
#             reference_days = pd.to_datetime(all_days[all_days.weekday >= 5])
#             sub = raw[raw["DATA"].isin(reference_days)]
#         else:
#             raise ValueError(f"Unknown seasonality={seasonality!r}")

#         sub_agg = sub.groupby("ID_COMUNE")[phenom.name].agg(phenom.agg)
#         total_agg = df.set_index("ID_COMUNE")[phenom.name]
#         sub_agg = sub_agg.reindex(total_agg.index).fillna(0)

#         return (sub_agg / total_agg.replace(0, np.nan)).values


# class CrowdingIndicator(Indicator):
#     """Computes the crowding index as sum of scores calculated based on turisticita', ricettivita', stagionalita', flussi"""

#     name = "Indice di affollamento"
#     description = "L'indice complessivo di affollamento turistico estivo integra e aggrega diversi indici legati all'affollamento turistico (ricettività, turisticità, stagionalità e flussi di escursionisti)."

#     def __init__(
#         self, structures_source, population_source, PRESENCES_SOURCE, flows_source
#     ):
#         self._top_indicators = [
#             AccommodationCapacityIndicator(structures_source, population_source),
#             TourismIndexIndicator(
#                 population_source,
#                 PRESENCES_SOURCE,
#                 presences_col_name="presenze_vodafone",
#             ),
#             SeasonalityIndicator(PRESENCES_SOURCE),
#         ]
#         self._max_indicator = FlowsIndicatorLevel(
#             flows_source, col="LEVEL_IN_VISITORS", flow_col="FLOWS_IN_VISITORS"
#         )
#         super().__init__(
#             phenomena=[*self._top_indicators, self._max_indicator],
#             combinator=self.compute_score,
#         )

#     def _compute_top(self, df: pd.DataFrame, **_extra) -> pd.Series:
#         """Compute top quantile score"""
#         df["score"] = 0
#         for indicator in self._top_indicators:
#             for q in [0.75, 0.875, 0.9375]:
#                 target_phen_name = indicator.name
#                 thr = df[target_phen_name].quantile(q)
#                 df["score"] += df[target_phen_name].ge(thr).fillna(False).astype(int)
#         return df

#     def _compute_max(self, df: pd.DataFrame, **_extra):
#         """Assingns 2 points to the places with max level of flows"""
#         col = self._max_indicator.name  # flussi
#         df.loc[df[col] == df[col].max(), "score"] += 2  # estrae il massimo
#         return df

#     def compute_score(self, df: pd.DataFrame, **_extra) -> pd.Series:
#         """Computes the total score of crowding index"""
#         df = self._compute_top(df)
#         df = self._compute_max(df)
#         return df["score"]
