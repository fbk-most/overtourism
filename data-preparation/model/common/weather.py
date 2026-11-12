# SPDX-License-Identifier: Apache-2.0
"""Weather sources shared by the model pipelines (standardization only, no modelling choices)."""

import pandas as pd


def standardize_meteo_station(path) -> pd.DataFrame:
    """Meteotrentino station series (data_download/download_meteo_meteotrentino.py) -> date, tmin,
    tmax, rain_mm, quality code (as delivered; the codes are not documented)."""
    out = pd.read_csv(path)
    out["date"] = pd.to_datetime(out["date"], format="%Y-%m-%d")
    return out[["date", "tmin", "tmax", "rain_mm", "quality"]].sort_values("date").reset_index(drop=True)


def standardize_meteo_bulletin(path, comune: str) -> pd.DataFrame:
    """Meteotrentino bulletin per comune (rounded values, text description)."""
    raw = pd.read_csv(path)
    raw = raw[raw["comune"] == comune]
    return pd.DataFrame({
        "date": pd.to_datetime(raw["data"]).dt.normalize(),
        "weather_desc": raw["meteo"],
        "tmin": raw["tmin"],
        "tmax": raw["tmax"],
        "rain_mm": raw["pioggiamm"],
    }).sort_values("date").reset_index(drop=True)
