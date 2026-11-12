# SPDX-License-Identifier: Apache-2.0
"""Time window of the data (see `period` in config/settings.yaml).

`clip(df, window)` keeps the rows whose DATA is inside the window:
  - yearly data (DATA = YYYY, int or str): kept if the YEAR is between window.start.year and window.end.year
  - daily data (DATA = YYYY-MM-DD, or a timestamp): kept if start <= DATA <= end (both included)
Rows with a missing / unparsable DATA are dropped.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Window:
    start: pd.Timestamp
    end: pd.Timestamp

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError(f"window start {self.start} is after its end {self.end}")

    def __str__(self):
        return f"{self.start:%Y-%m-%d}..{self.end:%Y-%m-%d}"

    def intersect(self, other: "Window") -> "Window":
        return Window(max(self.start, other.start), min(self.end, other.end))


def keep_mask(values: pd.Series, window: Window) -> pd.Series:
    """Boolean mask of the DATA values inside the window (see the module docstring)."""
    s = values.astype(str).str.strip()
    yearly = s.str.fullmatch(r"\d{4}(\.0)?")
    year = pd.to_numeric(s.str[:4], errors="coerce")
    day = pd.to_datetime(s, errors="coerce")
    if getattr(day.dt, "tz", None) is not None:
        day = day.dt.tz_localize(None)
    by_year = (year >= window.start.year) & (year <= window.end.year)
    by_day = (day >= window.start) & (day <= window.end)
    return pd.Series(np.where(yearly, by_year, by_day), index=values.index)


def clip(df: pd.DataFrame, window: Window, col: str = "DATA", name: str = "") -> pd.DataFrame:
    """Rows of `df` inside the window (new index), logging how many were discarded."""
    keep = keep_mask(df[col], window)
    n_out = int((~keep).sum())
    if n_out:
        logger.info(
            "[%s] %d/%d rows outside %s discarded", name or "window", n_out, len(df), window
        )
    return df[keep].reset_index(drop=True)
