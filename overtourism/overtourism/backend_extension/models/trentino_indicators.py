from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from overtourism.overtourism.backend_extension.models.indicator import Indicator
from overtourism.overtourism.backend_extension.models.phenomenon import Phenomenon

# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------
data_dir = (
    Path(__file__).resolve().parents[4]
    / "overtourism"
    / "overtourism"
    / "database"
    / "index_data_v2"
)  # TODO: replace this with dataloader

# _VODAFONE_ID_PREFIXES = [
#     'ratio',
#     'level',
#     'flows'
# ]

MAP_SHAPEFILE = data_dir / "Com01012026_g" / "Com01012026_g_WGS84.shp"
MAP_IDS = data_dir / "cities_gdf_base_columns.geojson"
POPULATION_SOURCE = data_dir / "phen_popolazione.parquet"
STRUCTURES_SOURCE = data_dir / "phen_strutture.parquet"
ATTENDENCES_SOURCE = data_dir / "phen_presenze.parquet"
FLOWS_SOURCE = data_dir / "phen_flussi.parquet"
MACRO_AREAS_FILE = data_dir / "map_comuni_into_apt.json"
CODICI_COMUNI_FILE = data_dir / "mapping_comuni_ISTAT.json"

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

"""
TODO:
-flussi, con parametri aggiuntivi
- livello di affollamento
- ridistribuzione turisti
- massima antropizzazione????
- altri indici
    # "indice-stagionalita":              lambda: SeasonalityIndicator(MAIN_DATA_SOURCE),
    # "turismo-sommerso":                 lambda: HiddenTourismIndicator(MAIN_DATA_SOURCE, WIND_SOURCE, "TURISTI_TOTALI"),
"""

_VARIATION_RATE_KEY = "tasso-variazione"

_REGISTRY: dict[str, Callable[[], Indicator]] = {
    _VARIATION_RATE_KEY: lambda: VariationRateIndicator(),
    "tasso-ricettivita": lambda: AccommodationCapacityIndicator(
        STRUCTURES_SOURCE, POPULATION_SOURCE
    ),
    "indice-turisticita": lambda: TourismIndexIndicator(
        POPULATION_SOURCE, ATTENDENCES_SOURCE, "presenze_vodafone"
    ),
    "indice-stagionalita": lambda: SeasonalityIndicator(ATTENDENCES_SOURCE),
    "indice-ospitalita-strutture": lambda: HospitalityIndexFacilitiesIndicator(
        STRUCTURES_SOURCE
    ),
    "indice-ospitalita-letti": lambda: HospitalityIndexBedsIndicator(STRUCTURES_SOURCE),
    "indice-turismo-sommerso": lambda: HiddenTourismIndicator(ATTENDENCES_SOURCE),
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

_INDICATOR_CACHE: dict[str, Indicator] = {}


def get_indicator(key: str) -> Indicator:
    if key not in _INDICATOR_CACHE:
        if key not in _REGISTRY:
            raise KeyError(f"Unknown indicator '{key}'. Available: {sorted(_REGISTRY)}")
        _INDICATOR_CACHE[key] = _REGISTRY[key]()
    return _INDICATOR_CACHE[key]


# ---------------------------------------------------------------------------
# Concrete indicators
# ---------------------------------------------------------------------------


class AccommodationCapacityIndicator(Indicator):
    """Beds per resident: NUMLETTI_TOT / POPOLAZIONE."""

    name = "Indice di ricettività"

    description = "L'indice di ricettività definisce il <strong>rapporto</strong> fra i <strong>letti presenti negli esercizi ricettivi<strong> e gli <strong>abitanti<strong> di una stessa area. L'indice è una misura della capacità turistica rispetto alla dimensione, in termini di popolazione, di un'area. L'indice è calcolato partendo dai dati ISPAT relativi alla popolazione residente e alla consistenza degli esercizi alberghieri e extra-alberghieri."

    def __init__(self, source_file1, source_file2):
        super().__init__(
            phenomena=[
                BedsPhenomenon(source_file1),
                PopulationPhenomenon(source_file2),
            ],
            combinator=self.divide("beds", "population"),
        )


class TourismIndexIndicator(Indicator):
    """Total presences per resident."""

    name = "Indice di turisticità"
    description = "L'indice di turisticità definisce il <strong>rapporto</strong> fra il <strong>numero medio giornaliero di turisti negli esercizi ricettivi<strong> e gli <strong>abitanti<strong> di una stessa area. L'indice è una misura dell'effettivo peso del turismo rispetto alla dimensione, in termini di popolazione, di un'area. L'indice è calcolato partendo dai dati Vodafone per quanto riguarda le presenze turistiche e dai dati ISPAT relativi alla popolazione residente."

    def __init__(self, source_file1, source_file2, presences_col_name):
        super().__init__(
            phenomena=[
                PresencesPhenomenon(source_file2, presences_col_name),
                PopulationPhenomenon(source_file1),
            ],
            combinator=self.divide("presences", "population"),
        )


class HospitalityIndexFacilitiesIndicator(Indicator):
    """Share of non-hotel facilities over total facilities."""

    name = "Indice di incidenza ospitalità non convenzionale (strutture)"
    description = "Questo indice di incidenza dell'ospitalità non convenzionale misura il <strong>rapporto</strong> fra le <strong>strutture ricettive non convenzionali<strong> e il <strong>totale delle strutture<strong> presenti in un'area. L'indice è calcolato partendo dai dati ISPAT relativi alla consistenza degli esercizi alberghieri e extra-alberghieri."

    def __init__(self, source_file):
        super().__init__(
            phenomena=[
                ExtraFacilitiesPhenomenon(source_file),
                FacilitiesTotalPhenomenon(source_file),
            ],
            combinator=self.divide("extra_Facilities", "Facilities_total"),
        )


class HospitalityIndexBedsIndicator(Indicator):
    """Share of non-hotel beds over total beds."""

    name = "Indice di incidenza ospitalità non convenzionale (posti letto)"
    description = "Questo indice di incidenza dell'ospitalità non convenzionale misura il <strong>rapporto<strong> fra il <strong>numero di posti letto in strutture ricettive non convenzionali<strong> e il <strong>numero totale di posti letto<strong> in tutte le strutture di un'area. L'indice è calcolato partendo dai dati ISPAT relativi alla consistenza degli esercizi alberghieri e extra-alberghieri."

    def __init__(self, source_file):
        super().__init__(
            phenomena=[
                ExtraBedsPhenomenon(source_file),
                BedsPhenomenon(source_file),
            ],
            combinator=self.divide("extra_beds", "beds"),
        )


class HiddenTourismIndicator(Indicator):
    """Calculates the hidden tourism indicator as the ratio between Vodafone registered attendences and accomodancy ones"""

    name = "Indice di turismo sommerso"
    description = "L'indice misura il <strong>rapporto<strong> fra le <strong>presenze di turisti misurate<strong> attraverso l'analisi di dati da rete di telefonia mobile e le <strong>presenze ufficiali<strong> di turisti in strutture alberghiere e extra-alberghiere. L'analisi è a livello di ambito turistico e riguarda gli anni 2022 e 2023. L'indice è stato calcolato partendo dai dati ISPAT sul movimento turistico e dai dati Vodafone relativi alle presenze misurate."

    def __init__(self, source_file):
        super().__init__(
            phenomena=[
                PresencesPhenomenon(
                    source_file, col="presenze_vodafone", name="presenze_vodafone"
                ),
                PresencesPhenomenon(
                    source_file,
                    col="presenze_alb_distributed",
                    name="presenze_alb",
                ),
                PresencesPhenomenon(
                    source_file,
                    col="presenze_xalb_distributed",
                    name="presenze_xalb",
                ),
            ],
            combinator=self.compute_hidden_factor,
        )

    def compute_hidden_factor(
        self,
        df: pd.DataFrame,
        **extra,
    ) -> pd.Series:
        return df["presenze_vodafone"] / (df["presenze_alb"] + df["presenze_xalb"])


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
            f"Livello flussi {col.removeprefix('LEVEL').replace('_', ' ').lower()}"
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


class SeasonalityIndicator(Indicator):
    """Sum of arrivals in a reference sub-period over total arrivals."""

    name = "Indice di stagionalità delle presenze"
    description = "L'indice di stagionalità definisce il <strong>rapporto</strong> fra le <strong>presenze di turisti ed escursionisti durante tra due periodi<strong> (es: anno completo ed alta stagione). L'indice è calcolato partendo dai dati Vodafone relativi alle presenze di turisti ed escursionisti."
    availableForVariation = False
    extraFields = ["seasonality"]

    def __init__(self, source_file):
        self._phenom = PresencesPhenomenon(source_file, col="presenze_vodafone")
        super().__init__(
            phenomena=[self._phenom],
            combinator=self.reference_period_over_total,
        )

    def reference_period_over_total(
        self,
        df: pd.DataFrame,
        filtered_data: dict[str, pd.DataFrame],
        start_date=None,
        end_date=None,
        seasonality: str = "high",
        **extra,
    ) -> pd.Series:
        phenom = self._phenom
        raw = filtered_data[phenom.name]  # already daily × comune panel slice

        MONTHLY_PERIODS = {
            "high": [7, 8],
            "shoulder": [4, 5, 6, 9, 10],
        }

        if seasonality in MONTHLY_PERIODS:
            months = MONTHLY_PERIODS[seasonality]
            sub = raw[raw["DATA"].dt.month.isin(months)]
        elif seasonality == "weekend":
            all_days = pd.date_range(start=start_date, end=end_date)
            reference_days = pd.to_datetime(all_days[all_days.weekday >= 5])
            sub = raw[raw["DATA"].isin(reference_days)]
        else:
            raise ValueError(f"Unknown seasonality={seasonality!r}")

        sub_agg = sub.groupby("ID_COMUNE")[phenom.name].agg(phenom.agg)
        total_agg = df.set_index("ID_COMUNE")[phenom.name]
        sub_agg = sub_agg.reindex(total_agg.index).fillna(0)

        return (sub_agg / total_agg.replace(0, np.nan)).values


class VariationRateIndicator(Indicator):
    """
    Generic "Tasso di variazione" (rate of variation) index.

    Computes the percentage change of *any other registered indicator*
    between two periods: the request's regular baseline period
    (``start_date`` / ``end_date``) and a comparison period
    (``start_date_comparison`` / ``end_date_comparison``). The same
    indicator is used as the phenomenon in both periods.

    Rather than hard-coding one variation subclass per wrapped indicator,
    the wrapped indicator is itself a parameter: it is selected at request
    time via the ``indicator`` extra field (its registry key, e.g.
    ``"indice-turisticita"``) — exactly like ``seasonality`` is an extra
    field on ``SeasonalityIndicator`` above. This keeps a single
    "tasso-variazione" entry in the registry that works for every
    combinable indicator.

    Because the wrapped indicator is only known once a request comes in,
    this class doesn't use the phenomena/combinator pipeline from the base
    class at all — ``_compute_indicator`` is fully overridden below, and
    ``phenomena``/``combinator`` are left empty/no-op.
    """

    name = "Tasso di variazione"
    description = "Il tasso di variazione misura la <strong>variazione percentuale</strong> di un indicatore fra il <strong>periodo selezionato</strong> ed un <strong>periodo storicizzato di confronto</strong>. È utile per confrontare due intervalli temporali (es. due stagioni, due anni) sullo stesso indice."
    availableForVariation = False
    extraFields = ["indicator", "start_date_comparison", "end_date_comparison"]
    internal_only = True

    def __init__(self):
        # No fixed phenomena: which indicator (and therefore which
        # phenomena) to use is only known at request time, via the
        # "indicator" extra field handled in _compute_indicator().
        super().__init__(phenomena=[], combinator=self._unused_combinator)

    @staticmethod
    def _unused_combinator(df: pd.DataFrame, **_extra) -> pd.Series:  # pragma: no cover
        # Never invoked: _compute_indicator() is fully overridden below and
        # bypasses the base class's phenomena-driven pipeline entirely.
        raise RuntimeError(
            "VariationRateIndicator.combinator should never be called directly"
        )

    @property
    def years_range(self) -> dict[str, int]:
        """
        Broadest year range across every combinable indicator in the
        registry (excluding this one), since the actual wrapped indicator
        isn't known until request time. Validity of the *chosen* indicator
        for the requested dates is enforced in ``_compute_indicator``.
        """
        if self._years_range is None:
            min_years, max_years = [], []
            for key in _REGISTRY:
                if key == _VARIATION_RATE_KEY:
                    continue
                try:
                    yr = get_indicator(key).years_range
                except ValueError:
                    continue
                min_years.append(yr["min_year"])
                max_years.append(yr["max_year"])

            if not min_years:
                raise ValueError(
                    f"{self!r}: no combinable indicators available to compute "
                    "a years_range for"
                )

            self._years_range = {
                "min_year": min(min_years),
                "max_year": max(max_years),
            }
        return self._years_range

    def _compute_indicator(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **extra,
    ) -> pd.DataFrame | None:
        indicator_key = extra.pop("indicator", None)
        start_date_comparison = extra.pop("start_date_comparison", None)
        end_date_comparison = extra.pop("end_date_comparison", None)

        if not indicator_key:
            raise ValueError(
                "'indicator' extra field is required for 'tasso-variazione'"
            )
        if indicator_key == _VARIATION_RATE_KEY:
            raise ValueError("'tasso-variazione' cannot wrap itself")
        if start_date_comparison is None or end_date_comparison is None:
            raise ValueError(
                "'start_date_comparison' and 'end_date_comparison' extra "
                "fields are required for 'tasso-variazione'"
            )

        wrapped = get_indicator(indicator_key)

        # Current period (e.g. 2025)
        current_df = wrapped.get_indicator(
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

        # Reference period (e.g. 2024)
        previous_df = wrapped.get_indicator(
            start_date=start_date_comparison,
            end_date=end_date_comparison,
            **extra,
        )

        if current_df is None or previous_df is None:
            return None

        merged = current_df[["ID_COMUNE", "INDICE"]].merge(
            previous_df[["ID_COMUNE", "INDICE"]],
            on="ID_COMUNE",
            how="outer",
            suffixes=("_current", "_previous"),
        )

        # Percentage variation: (current - previous) / previous * 100
        merged["INDICE"] = (
            (merged["INDICE_current"] - merged["INDICE_previous"])
            / merged["INDICE_previous"].replace(0, np.nan)
        ) * 100

        return merged[["ID_COMUNE", "INDICE"]]


# ---------------------------------------------------------------------------
# Concrete phenomena
# ---------------------------------------------------------------------------


class PresencesPhenomenon(Phenomenon):
    """Total presences (tourists, excursionists, or combined)."""

    name = "presences"
    # Native resolution: daily × comune  →  both axes are 'identity'
    temporal_resolution = "daily"
    temporal_strategy = "identity"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="presenze", name=None):
        super().__init__(source, col, agg="mean")
        if name is not None:
            self.name = name


# class ArrivalsPhenomenon(Phenomenon):
#     """Total arrivals."""

#     name = "arrivals"
#     temporal_resolution = "daily"
#     temporal_strategy = "identity"
#     spatial_resolution = "comune"
#     spatial_strategy = "identity"

#     def __init__(self, source, col="NUMARRIVATI_TOT"):
#         super().__init__(source, col, agg="sum")


class BedsPhenomenon(Phenomenon):
    """Total beds (all accommodation types)."""

    name = "beds"
    # Beds don't change day-to-day within a period; treat as constant daily.
    # If the source is already daily, temporal_strategy='identity' is fine too.
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_postiletto"):
        super().__init__(source, col, agg="mean")


class ExtraBedsPhenomenon(Phenomenon):
    """Beds in non-hotel (extra-alberghiero) facilities."""

    name = "extra_beds"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_postiletto_non_conv"):
        super().__init__(source, col, agg="mean")


class FacilitiesTotalPhenomenon(Phenomenon):
    """Total accommodation facilities."""

    name = "Facilities_total"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_strutture"):
        super().__init__(source, col, agg="mean")


class ExtraFacilitiesPhenomenon(Phenomenon):
    """Non-hotel facilities."""

    name = "extra_Facilities"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_strutture_non_conv"):
        super().__init__(source, col, agg="mean")


class PopulationPhenomenon(Phenomenon):
    """
    Resident population.
    """

    name = "population"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"  # broadcast uniformly across days
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="popolazione"):
        super().__init__(
            source,
            col,
            agg="mean",
            dtype={"LOCATION_ID": str},
        )


class FlowPhenomenon(Phenomenon):
    """Flows in/out + users"""

    name = "flows"
    temporal_strategy = "constant"
    temporal_resolution = "yearly"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(
        self, source, col="flows", municipality_id_col="ID", name=None, agg="mean"
    ):  # TODO: check why mean works and not sum
        super().__init__(
            source,
            col,
            agg=agg,
            municipality_id_col=municipality_id_col,
        )
        if name is not None:
            self.name = name
