# SPDX-License-Identifier: Apache-2.0
"""Adapters for the popolazione (residents) source."""

import pandas as pd

from data_preparation.utils.adapters.base import RawData, register_adapter


@register_adapter("popolazione_ispat_1jan", kind="popolazione")
def popolazione_ispat_1jan(
    raw: RawData, *, year: int, population_col: str | None = None, comune_col: str = "Comuni"
) -> pd.DataFrame:
    """ISPAT residents table, one column per 1 January; the 1.1.<year> column is assigned to `year`."""
    population_col = population_col or f"Popolazione residente al 1.1.{year}"
    df = raw.df.copy()
    df = df.rename(columns={comune_col: "comune", population_col: "popolazione"}).sort_values(
        by="comune"
    )
    df["anno"] = year
    return df[["comune", "popolazione", "anno"]]


def popolazione_arithmetic_mean(df: pd.DataFrame, col_from: str, col_to: str) -> pd.Series:
    """Rounded arithmetic mean of two 1 January columns (not used by the pipeline, kept as a helper
    for sources that need a year-average instead of the 1 January value)."""
    return ((df[col_from] + df[col_to]) / 2).round().astype(int)
