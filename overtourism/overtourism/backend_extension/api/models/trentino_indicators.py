from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from overtourism.overtourism.backend_extension.api.models.indicator import Indicator
from overtourism.overtourism.backend_extension.api.models.trenitno_phenomena import (
    BedsPhenomenon,
    ExtraBedsPhenomenon,
    ExtraFacilitiesPhenomenon,
    FacilitiesTotalPhenomenon,
    PopulationPhenomenon,
    PresencesPhenomenon,
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
# Types definition
# ---------------------------------------------------------------------------
INDICATORS_TYPES = [
    "Gestione della Sostenibilità",
    "Impatti socio-economici",
    "Impatti culturali",
    "Impatti ambientali",
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_VARIATION_RATE_KEY = "tasso-variazione"
_PERIOD_PERCENTAGE_IMPACT_KEY = "incidenza-periodo"

_REGISTRY: dict[str, Callable[[], Indicator]] = {
    "ricettivita": lambda: AccommodationCapacityIndicator(
        STRUCTURES_SOURCE, POPULATION_SOURCE
    ),
    "turisticita": lambda: TourismIndexIndicator(
        POPULATION_SOURCE, PRESENCES_SOURCE, "presenze_vodafone"
    ),
    "ospitalita-strutture": lambda: HospitalityIndexFacilitiesIndicator(
        STRUCTURES_SOURCE
    ),
    "ospitalita-letti": lambda: HospitalityIndexBedsIndicator(STRUCTURES_SOURCE),
    "turismo-sommerso": lambda: HiddenTourismIndicator(PRESENCES_SOURCE),
    _VARIATION_RATE_KEY: lambda: VariationRateIndicator(),
    _PERIOD_PERCENTAGE_IMPACT_KEY: lambda: PeriodPercentageImpactIndicator(),
}

if INCLUDE_TEMP_REGISTRY:
    from overtourism.overtourism.backend_extension.api.models.trentino_indicators_temp import (
        _REGISTRY_TEMP,
    )

    _REGISTRY.update(_REGISTRY_TEMP)

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
    type = INDICATORS_TYPES[1]
    description = "L'indice di ricettività definisce il <strong>rapporto</strong> fra i <strong>letti presenti negli esercizi ricettivi</strong> e gli <strong>abitanti</strong> di una stessa area. L'indice è una misura della capacità turistica rispetto alla dimensione, in termini di popolazione, di un'area. L'indice è calcolato partendo dai dati ISPAT relativi alla popolazione residente e alla consistenza degli esercizi alberghieri e extra-alberghieri."
    index_value_unit_description = "Rapporto posti letto / popolazione"

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
    type = INDICATORS_TYPES[1]
    description = "L'indice di turisticità definisce il <strong>rapporto</strong> fra il <strong>numero medio giornaliero di turisti negli esercizi ricettivi</strong> di una specifica area e il<strong>numero di abitanti</strong> della stessa area. L'indice fornisce una misura dell'effettiva incidenza del turismo rispetto alla dimensione, in termini di popolazione, di un'area. L'indice è calcolato partendo dai dati Vodafone per quanto riguarda le presenze turistiche e dai dati ISPAT relativi alla popolazione residente."
    index_value_unit_description = "Rapporto fra numero turisti e popolazione"

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
    type = INDICATORS_TYPES[1]
    description = "Questo indice di incidenza dell'ospitalità non convenzionale misura il <strong>rapporto</strong> fra il  <strong>numero di strutture ricettive non convenzionali</strong> e il <strong>numero totale delle strutture</strong> presenti in un'area. L'indice è calcolato partendo dai dati ISPAT relativi al numero degli esercizi alberghieri e extra-alberghieri."
    index_value_unit_description = (
        "Percentuale strutture ricettive non conv. rispetto al totale"
    )

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
    type = INDICATORS_TYPES[1]
    description = "Questo indice di incidenza dell'ospitalità non convenzionale misura il <strong>rapporto</strong> fra il <strong>numero di posti letto in strutture ricettive non convenzionali</strong> e il <strong>numero totale di posti letto</strong> in tutte le strutture di un'area. L'indice è calcolato partendo dai dati ISPAT al numero degli esercizi alberghieri e extra-alberghieri."
    index_value_unit_description = (
        "Percentuale letti in strututre ricettive non conv. rispetto al totale"
    )

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
    type = INDICATORS_TYPES[0]
    description = "L'indice misura il <strong>rapporto</strong> fra le <strong>presenze di turisti misurate</strong> attraverso l'analisi di dati da rete di telefonia mobile e le <strong>presenze ufficiali</strong> di turisti in strutture alberghiere e extra-alberghiere. L'indice è stato calcolato partendo dai dati ISPAT sul movimento turistico e dai dati Vodafone relativi alle presenze misurate."
    index_value_unit_description = "Rapporto fra presenze misurate e ufficiali"

    def __init__(self, source_file):
        super().__init__(
            phenomena=[
                PresencesPhenomenon(
                    source_file, col="presenze_vodafone", name="presenze_vodafone"
                ),
                PresencesPhenomenon(
                    source_file,
                    col="presenze_alb",
                    name="presenze_alb",
                ),
                PresencesPhenomenon(
                    source_file,
                    col="presenze_xalb",
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
    index_value_unit_description = "Percentuale di variazione tra due periodi"

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

        merged = (
            current_df[["ID_COMUNE", "INDICE"]]
            .rename(columns={"INDICE": "Periodo base"})
            .merge(
                previous_df[["ID_COMUNE", "INDICE"]].rename(
                    columns={"INDICE": "Periodo comparazione"}
                ),
                on="ID_COMUNE",
                how="outer",
            )
        )

        # Percentage variation: (baseline - comparison) / comparison * 100
        merged["INDICE"] = (
            (merged["Periodo base"] - merged["Periodo comparazione"])
            / merged["Periodo comparazione"].replace(0, np.nan)
        ) * 100

        return merged[["ID_COMUNE", "INDICE", "Periodo base", "Periodo comparazione"]]


class PeriodPercentageImpactIndicator(Indicator):
    """
    Percentage weight that a seasonal sub-period has on the total value of
    another indicator over the full requested period.

    Hybrid of VariationRateIndicator (wrapped indicator selected at request
    time via the "indicator" extra field) and SeasonalityIndicator (result
    expresses a sub-period's share of a total period, via "seasonality").

    result = 100 * INDICE(wrapped, full_period, seasonality=X)
                 / INDICE(wrapped, full_period, no seasonality filter)
    """

    name = "Incidenza percentuale del periodo"
    description = (
        "L'incidenza percentuale del periodo misura il <strong>peso "
        "percentuale</strong> che un <strong>sotto-periodo stagionale</strong> "
        "(es. alta stagione, periodo di spalla, weekend) ha sul "
        "<strong>totale del periodo selezionato</strong>, per un indicatore "
        "a scelta."
    )
    availableForVariation = False
    extraFields = ["indicator", "seasonality"]
    internal_only = True
    index_value_unit_description = (
        "Percentuale di impatto del sottoperiodo rispetto al periodo totale"
    )

    def __init__(self):
        # Same rationale as VariationRateIndicator: the wrapped indicator is
        # only known at request time via the "indicator" extra field, so the
        # base class's phenomena/combinator pipeline is bypassed entirely.
        super().__init__(phenomena=[], combinator=self._unused_combinator)

    @staticmethod
    def _unused_combinator(df: pd.DataFrame, **_extra) -> pd.Series:  # pragma: no cover
        raise RuntimeError(
            "PeriodPercentageImpactIndicator.combinator should never be called directly"
        )

    @property
    def years_range(self) -> dict[str, int]:
        """Broadest year range across every combinable indicator, same
        rationale as VariationRateIndicator.years_range."""
        if self._years_range is None:
            min_years, max_years = [], []
            for key in _REGISTRY:
                if key == _PERIOD_PERCENTAGE_IMPACT_KEY:
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
        seasonality = extra.pop("seasonality", None)

        if not indicator_key:
            raise ValueError(
                "'indicator' extra field is required for 'incidenza-periodo'"
            )
        if indicator_key == _PERIOD_PERCENTAGE_IMPACT_KEY:
            raise ValueError("'incidenza-periodo' cannot wrap itself")
        if indicator_key == _VARIATION_RATE_KEY:
            # Not strictly wrong, but tasso-variazione already needs its own
            # extra fields (start/end_date_comparison); reject early with a
            # clear message rather than a confusing missing-field error.
            raise ValueError("'incidenza-periodo' cannot wrap 'tasso-variazione'")
        if not seasonality:
            raise ValueError(
                "'seasonality' extra field is required for 'incidenza-periodo'"
            )

        wrapped = get_indicator(indicator_key)

        total_df = wrapped.get_indicator(
            start_date=start_date,
            end_date=end_date,
            **extra,
        )
        seasonal_df = wrapped.get_indicator(
            start_date=start_date,
            end_date=end_date,
            seasonality=seasonality,
            **extra,
        )

        if total_df is None or seasonal_df is None:
            return None

        merged = (
            total_df[["ID_COMUNE", "INDICE"]]
            .rename(columns={"INDICE": "INDICE_total"})
            .merge(
                seasonal_df[["ID_COMUNE", "INDICE"]].rename(
                    columns={"INDICE": "INDICE_seasonal"}
                ),
                on="ID_COMUNE",
                how="outer",
            )
        )
        merged["INDICE_seasonal"] = merged["INDICE_seasonal"].fillna(0)

        merged["INDICE"] = (
            merged["INDICE_seasonal"] / merged["INDICE_total"].replace(0, np.nan)
        ) * 100

        return merged[["ID_COMUNE", "INDICE", "INDICE_total", "INDICE_seasonal"]]
