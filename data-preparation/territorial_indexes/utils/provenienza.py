# SPDX-License-Identifier: Apache-2.0
"""Index "Provenienza - Indice di concentrazione mercati provenienza" (concentration of the source markets).

Source: Vodafone presences (`vodafone_attendences`), TOURIST profile, area level, per day x area x `userCountry`.
Pure functions, no I/O. Per YEAR and Vodafone AREA:

  s_c   = presences of country c / presences of all the countries (user-days summed over the year)
  H     = sum_c s_c^2                              Herfindahl-Hirschman index, 1/N <= H <= 1
  hhi   = (H - 1/N) / (1 - 1/N)                    normalized HHI, 0 = presences spread evenly over the N
                                                   markets, 1 = a single market; N = markets with presences > 0
                                                   (N = 1 -> 1)

The index is NaN where the area has fewer than `min_presenze` user-days in the year (too few for reliable
shares; the Vodafone counts are also censored below a privacy threshold, so small areas are the most biased).
The HHI is not additive: an area is NOT split among its comuni. An area passes its value to ALL its comuni; a
comune with several areas gets the mean weighted by the user-days of the areas.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HHI_COL = "hhi_provenienza"


def normalized_hhi(shares_by_group: pd.DataFrame) -> pd.Series:
    """Normalized HHI per group. `shares_by_group` has the columns `key` (any group id), `value` (> 0)."""
    tot = shares_by_group.groupby("key")["value"].transform("sum")
    sq = (shares_by_group["value"] / tot) ** 2
    h = sq.groupby(shares_by_group["key"]).sum()
    n = shares_by_group.groupby("key")["value"].size()
    inv_n = 1.0 / n
    out = (h - inv_n) / (1.0 - inv_n.where(n > 1, 0.0)).where(n > 1, 1.0)
    out[n == 1] = 1.0
    return out.clip(lower=0.0, upper=1.0)


def area_hhi(df: pd.DataFrame, min_presenze: float) -> pd.DataFrame:
    """Rows (DATA, areaId, userCountry, value) -> one row per (year, areaId): `hhi`, `presenze` (user-days),
    `n_mercati`. `hhi` is NaN below `min_presenze`."""
    year = df["DATA"].astype(str).str[:4].astype(int)
    yearly = (
        df.assign(year=year)
        .groupby(["year", "areaId", "userCountry"], as_index=False, observed=True)["value"]
        .sum()
    )
    tot = yearly.groupby(["year", "areaId"], as_index=False)["value"].sum().rename(
        columns={"value": "presenze"}
    )
    pos = yearly[yearly["value"] > 0].copy()
    pos["key"] = list(zip(pos["year"], pos["areaId"]))
    hhi = normalized_hhi(pos)
    keys = pd.DataFrame(hhi.index.tolist(), columns=["year", "areaId"])
    keys["hhi"] = hhi.to_numpy()
    keys["n_mercati"] = pos.groupby("key").size().reindex(hhi.index).to_numpy()
    out = tot.merge(keys, on=["year", "areaId"], how="left")
    out.loc[out["presenze"] < min_presenze, "hhi"] = np.nan
    return out


def comune_hhi(df: pd.DataFrame, area_comune: pd.DataFrame, min_presenze: float) -> pd.DataFrame:
    """Standardized rows (DATA, areaId, userCountry, value) -> (DATA = year, ID_COMUNE, hhi_provenienza,
    giorni_coperti). `area_comune`: areaId, ID_COMUNE (an area may have several comuni)."""
    if df.empty:
        raise ValueError("[provenienza] no presences to process")
    coverage = (
        df.assign(year=df["DATA"].astype(str).str[:4].astype(int))
        .groupby("year")["DATA"]
        .nunique()
        .rename("giorni_coperti")
    )
    areas = area_hhi(df, min_presenze)
    unmapped = sorted(set(areas["areaId"]) - set(area_comune["areaId"]))
    if unmapped:
        logger.warning(
            "[provenienza] areas with no comune (absent from the comune data): %s", unmapped
        )
    m = areas.merge(area_comune, on="areaId", how="inner")
    m = m[m["hhi"].notna() & (m["presenze"] > 0)]
    m["_wh"] = m["hhi"] * m["presenze"]
    g = m.groupby(["year", "ID_COMUNE"], as_index=False)[["_wh", "presenze"]].sum()
    g[HHI_COL] = g["_wh"] / g["presenze"]
    g["DATA"] = g["year"].astype(int)
    g["giorni_coperti"] = g["DATA"].map(coverage).astype(int)
    return (
        g[["DATA", "ID_COMUNE", HHI_COL, "giorni_coperti"]]
        .sort_values(["DATA", "ID_COMUNE"])
        .reset_index(drop=True)
    )
