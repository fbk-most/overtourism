from __future__ import annotations

from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_CONFIG_FILE = (
    Path(__file__).resolve().parents[6]
    / "data_preparation/territorial_indexes/config/settings.yaml"
)


@dataclass(frozen=True)
class AnnualCoverageSettings:
    active: bool
    min_comune_coverage: float


def load_annual_coverage_settings(
    path: Path = _CONFIG_FILE,
) -> AnnualCoverageSettings:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{path}: expected a mapping")

    annual_coverage = config.get("annual_coverage", True)
    if isinstance(annual_coverage, dict):
        active = annual_coverage.get("active")
        min_coverage = annual_coverage.get(
            "min_comune_coverage", config.get("min_comune_coverage", 0.5)
        )
    else:
        active = annual_coverage
        min_coverage = config.get("min_comune_coverage", 0.5)
    if not isinstance(active, bool):
        raise ValueError(f"{path}: annual_coverage must be true or false")
    if (
        isinstance(min_coverage, bool)
        or not isinstance(min_coverage, (int, float))
        or not 0 <= min_coverage <= 1
    ):
        raise ValueError(
            f"{path}: min_comune_coverage must be a number between 0 and 1"
        )
    return AnnualCoverageSettings(active, float(min_coverage))


def _expected_comuni(comuni: Iterable[object]) -> set[str]:
    expected = {str(comune) for comune in comuni}
    if not expected:
        raise ValueError("at least one comune is required to assess annual coverage")
    return expected


def _coverage_is_sufficient(
    covered_comuni: Iterable[object],
    expected_comuni: Iterable[object],
    min_coverage: float,
) -> bool:
    expected = _expected_comuni(expected_comuni)
    covered = {str(comune) for comune in covered_comuni} & expected
    return len(covered) / len(expected) >= min_coverage


def mask_annual_index_if_under_coverage(
    result: pd.DataFrame,
    *,
    year_only: bool,
    expected_comuni: Iterable[object],
    settings: AnnualCoverageSettings,
    excluded_values: Sequence[float] = (),
) -> pd.DataFrame:
    if not settings.active or settings.min_comune_coverage == 0 or not year_only:
        return result
    if not {"ID_COMUNE", "INDICE"}.issubset(result.columns):
        raise ValueError("annual indicator result must contain ID_COMUNE and INDICE")
    if result["ID_COMUNE"].duplicated().any():
        raise ValueError("annual indicator result contains duplicate comune rows")

    values = pd.to_numeric(result["INDICE"], errors="raise").to_numpy(dtype=float)
    valid = np.isfinite(values) & ~np.isin(values, excluded_values)
    covered = result.loc[valid, "ID_COMUNE"].astype(str)
    if _coverage_is_sufficient(covered, expected_comuni, settings.min_comune_coverage):
        return result

    masked = result.copy()
    masked["INDICE"] = np.nan
    return masked


def mask_annual_series_if_under_coverage(
    series: list[dict],
    *,
    labels: list[str],
    year_only: bool,
    expected_comuni: Iterable[object],
    settings: AnnualCoverageSettings,
    excluded_values: Sequence[float] = (),
) -> list[dict]:
    if not settings.active or settings.min_comune_coverage == 0 or not year_only:
        return series
    expected = _expected_comuni(expected_comuni)
    masked = deepcopy(series)
    comune_series = {
        str(item["label"]): item for item in masked if str(item["label"]) in expected
    }

    for index in range(len(labels)):
        covered = {
            comune
            for comune, item in comune_series.items()
            if item["data"][index] is not None
            and np.isfinite(float(item["data"][index]))
            and float(item["data"][index]) not in excluded_values
        }
        if not _coverage_is_sufficient(covered, expected, settings.min_comune_coverage):
            for item in masked:
                item["data"][index] = None
                if index < len(item.get("std", [])):
                    item["std"][index] = None
    return masked
