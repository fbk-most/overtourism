"""Apply the shared annual comune-coverage rule to indicator source columns."""

import logging
from collections.abc import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

GINI_PRESENCES_COLUMN = "presenze_vodafone_gini"

_ANNUAL_VALUE_RULES = {
    "phen_flussi_od": (
        ("quota di mobilità in ingresso", "quota_ingresso_combined", "quota_ingresso"),
        ("quota di mobilità in uscita", "quota_uscita_combined", "quota_uscita"),
        ("quota intra-ambito", "quota_intra_ambito_combined", "quota_intra_ambito"),
        ("centralità PageRank", "pagerank_combined", "pagerank"),
    ),
    "phen_provenienza": (
        ("concentrazione mercati di provenienza", "hhi_provenienza", None),
        ("dipendenza dal mercato principale", "volume_totale", "market"),
    ),
    "phen_ee_tourism_share": (
        ("quota consumi elettrici attribuibili al turismo", "quota_ee_turismo", None),
    ),
}


def _comune_id(value: object) -> str:
    text = str(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def _year_values(frame: pd.DataFrame) -> pd.Series:
    return frame["DATA"].astype(str).str[:4]


def _mask_undercovered_column_group(
    frame: pd.DataFrame,
    *,
    phenomenon: str,
    indicator: str,
    valid_column: str,
    related_columns: list[str],
    expected_comuni: set[str],
    min_coverage: float,
) -> set[str]:
    missing = (set(related_columns) | {valid_column}) - set(frame.columns)
    if missing:
        raise ValueError(f"{phenomenon} is missing annual coverage columns: {sorted(missing)}")
    if frame.duplicated(["DATA", "ID_COMUNE"]).any():
        raise ValueError(f"{phenomenon} must have one row per DATA and ID_COMUNE")

    excluded_years = set()
    comunes = frame["ID_COMUNE"].map(_comune_id)
    years = _year_values(frame)
    values = pd.to_numeric(frame[valid_column], errors="coerce")
    valid = np.isfinite(values)
    if indicator == "centralità PageRank":
        valid &= values > 0
    elif indicator == "dipendenza dal mercato principale":
        total = pd.to_numeric(frame["volume_totale"], errors="coerce")
        main = pd.to_numeric(frame["volume_mercato_1"], errors="coerce")
        valid &= np.isfinite(total) & np.isfinite(main) & (total >= 100)

    for year in sorted(years.unique()):
        year_mask = years == year
        covered = set(comunes[year_mask & valid]) & expected_comuni
        coverage = len(covered) / len(expected_comuni)
        if coverage >= min_coverage:
            continue
        excluded_years.add(year)
        frame.loc[year_mask, related_columns] = np.nan
        logger.warning(
            "[annual_coverage] excluding %s for %s: %.1f%% of comuni have a valid value "
            "(minimum %.1f%%)",
            year,
            indicator,
            coverage * 100,
            min_coverage * 100,
        )
    return excluded_years


def _gini_valid_comuni(frame: pd.DataFrame, year: str) -> set[str]:
    dates = pd.to_datetime(frame["DATA"])
    year_frame = frame.loc[dates.dt.year.astype(str) == year]
    expected_dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    valid_comuni = set()

    for comune, rows in year_frame.groupby("ID_COMUNE", sort=False):
        values = (
            rows.assign(DATA=pd.to_datetime(rows["DATA"]))
            .groupby("DATA")[GINI_PRESENCES_COLUMN]
            .mean()
            .reindex(expected_dates)
        )
        observed = values.dropna().to_numpy(dtype=float)
        if (
            values.notna().mean() >= 0.8
            and observed.size >= 2
            and np.isfinite(observed).all()
            and not (observed < 0).any()
            and observed.sum() > 0
        ):
            valid_comuni.add(_comune_id(comune))
    return valid_comuni


def _apply_gini_coverage(
    frame: pd.DataFrame,
    *,
    expected_comuni: set[str],
    min_coverage: float,
) -> None:
    if GINI_PRESENCES_COLUMN not in frame.columns:
        if "presenze_vodafone" not in frame.columns:
            raise ValueError(
                "phen_presenze needs presenze_vodafone to prepare the annual Gini input"
            )
        frame[GINI_PRESENCES_COLUMN] = frame["presenze_vodafone"]

    if not expected_comuni or min_coverage == 0:
        return

    years = _year_values(frame)
    for year in sorted(years.unique()):
        coverage = len(_gini_valid_comuni(frame, year) & expected_comuni) / len(
            expected_comuni
        )
        if coverage >= min_coverage:
            continue
        frame.loc[years == year, GINI_PRESENCES_COLUMN] = np.nan
        logger.warning(
            "[annual_coverage] excluding the seasonality Gini for %s: "
            "%.1f%% of comuni have a valid value (minimum %.1f%%)",
            year,
            coverage * 100,
            min_coverage * 100,
        )


def apply_annual_coverage(
    phenomena: dict[str, pd.DataFrame],
    *,
    expected_comuni: Iterable[object],
    active: bool,
    min_coverage: float,
) -> dict[str, pd.DataFrame]:
    """Mask only the annual index's own source columns when a year misses coverage."""
    if not isinstance(active, bool):
        raise ValueError("annual_coverage must be true or false")
    if (
        isinstance(min_coverage, bool)
        or not isinstance(min_coverage, (int, float))
        or not 0 <= min_coverage <= 1
    ):
        raise ValueError("min_comune_coverage must be between 0 and 1")
    if not active or min_coverage == 0:
        if "phen_presenze" in phenomena:
            _apply_gini_coverage(
                phenomena["phen_presenze"],
                expected_comuni=set(),
                min_coverage=0,
            )
        return phenomena

    eligible_frames = {
        name: frame
        for name, frame in phenomena.items()
        if name in {*_ANNUAL_VALUE_RULES, "phen_presenze"} and not frame.empty
    }
    if not eligible_frames:
        return phenomena

    expected = {_comune_id(comune) for comune in expected_comuni}
    if not expected:
        raise ValueError("at least one comune is required to assess annual coverage")

    if "phen_presenze" in phenomena:
        _apply_gini_coverage(
            phenomena["phen_presenze"],
            expected_comuni=expected,
            min_coverage=min_coverage,
        )

    for phenomenon, rules in _ANNUAL_VALUE_RULES.items():
        frame = phenomena.get(phenomenon)
        if frame is None or frame.empty:
            continue
        excluded_by_indicator = []
        for indicator, valid_column, related_group in rules:
            related_columns = (
                [column for column in frame if column.startswith(related_group)]
                if related_group is not None
                else [valid_column]
            )
            if indicator == "dipendenza dal mercato principale":
                related_columns = ["volume_mercato_1", "volume_totale"]
            excluded_by_indicator.append(
                _mask_undercovered_column_group(
                    frame,
                    phenomenon=phenomenon,
                    indicator=indicator,
                    valid_column=valid_column,
                    related_columns=related_columns,
                    expected_comuni=expected,
                    min_coverage=min_coverage,
                )
            )
        excluded_years = set.intersection(*excluded_by_indicator)
        if excluded_years:
            frame.drop(
                index=frame.index[_year_values(frame).isin(excluded_years)],
                inplace=True,
            )
    return phenomena