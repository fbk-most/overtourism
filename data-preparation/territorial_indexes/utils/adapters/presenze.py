# SPDX-License-Identifier: Apache-2.0
"""Adapter for the ISPAT monthly arrivals / presences files (alb and extralb).

These files are NOT normalized: the processing step reads them as downloaded
(see process_std_data.py: process_presenze_alb / process_presenze_extralb).
The adapter only declares what a file is (year, arrivals or presences) and checks its layout.
"""

import pandas as pd

from utils.adapters.base import RawData, register_adapter

MONTHS_MAPPING = {
    "Gennaio": 1,
    "Febbraio": 2,
    "Marzo": 3,
    "Aprile": 4,
    "Maggio": 5,
    "Giugno": 6,
    "Luglio": 7,
    "Agosto": 8,
    "Settembre": 9,
    "Ottobre": 10,
    "Novembre": 11,
    "Dicembre": 12,
}
MEASURES = ("arrivi", "presenze")


@register_adapter("ispat_presenze_raw", kind="presenze_raw")
def ispat_presenze_raw(raw: RawData, *, year: int, measure: str) -> pd.DataFrame:
    """ISPAT monthly table (mese + one '<territory> - Totale' column per territory), returned unchanged."""
    if measure not in MEASURES:
        raise ValueError(f"measure must be one of {MEASURES}, got {measure!r}")
    first = str(raw.df.columns[0]).strip().lower()
    if first != "mese":
        raise ValueError(
            f"Expected the first column to be 'mese', found {raw.df.columns[0]!r}"
        )
    return raw.df
