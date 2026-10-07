# SPDX-License-Identifier: Apache-2.0
"""Adapters for the ISPAT presences sources (APT-level and provincial, monthly)."""

import pandas as pd

from data_preparation.utils.adapters.base import RawData, register_adapter
from data_preparation.utils.cleaning import grouped_presenze_columns, remove_unnamed

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


@register_adapter("presenze_ispat_apt", kind="presenze_apt")
def presenze_ispat_apt(raw: RawData, *, year: int) -> pd.DataFrame:
    """Wide ISPAT table (Mese x APT, Italiani/Stranieri/Totale) -> long (Ambito, Anno, Mese, Presenze).
    Needs raw.meta['apts'] (first row of the file, as set by the 'ispat_apt_tsv' reader)."""
    apts = raw.meta["apts"]
    df = raw.df
    columns = grouped_presenze_columns(apts[1:])

    if len(columns) != df.shape[1]:
        raise ValueError(f"Expected {len(columns)} columns, found {df.shape[1]}")

    df = df.copy()
    df.columns = columns

    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Anno"].copy()
    mapped_months = df["Mese"].map(MONTHS_MAPPING)
    if mapped_months.isna().any():
        raise ValueError(f"Unrecognised months: {df.loc[mapped_months.isna(), 'Mese'].unique()}")
    df["Mese"] = mapped_months.astype(int)
    value_cols = [c for c in df.columns if c.endswith(" Totale")]

    long_df = df.melt(
        id_vars=["Mese"], value_vars=value_cols, var_name="Ambito", value_name="Presenze"
    )
    long_df["Ambito"] = long_df["Ambito"].str.removesuffix(" Totale").str.strip()
    long_df["Presenze"] = pd.to_numeric(long_df["Presenze"], errors="coerce")
    if long_df["Presenze"].isna().any():
        bad = long_df.loc[long_df["Presenze"].isna(), "Ambito"].unique()
        raise ValueError(f"Non-numeric values for ambiti: {bad}")

    long_df["Presenze"] = long_df["Presenze"].astype(int)
    long_df["Anno"] = year
    return long_df[["Ambito", "Anno", "Mese", "Presenze"]]


@register_adapter("presenze_ispat_prov", kind="presenze_prov")
def presenze_ispat_prov(
    raw: RawData,
    *,
    year: int,
    alb_col: str = "Esercizi alberghieri Totale",
    xalb_col: str = "Esercizi extralberghieri Totale",
) -> pd.DataFrame:
    """Provincial ISPAT table (alb / extra-alb per month) -> (Anno, Mese, Presenze alberghi, Presenze extra-alberghi)."""
    df = remove_unnamed(raw.df)
    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Totale"].reset_index(drop=True)
    df["Mese"] = df["Mese"].map(MONTHS_MAPPING)
    if df["Mese"].isna().any():
        raise ValueError(f"Unrecognised months: {df.loc[df['Mese'].isna(), 'Mese'].unique()}")

    for col in (alb_col, xalb_col):
        if col not in df.columns:
            raise ValueError(f"Expected column not found: {col}")

    out = pd.DataFrame(
        {
            "Anno": year,
            "Mese": df["Mese"].astype(int),
            "Presenze alberghi": pd.to_numeric(df[alb_col], errors="coerce"),
            "Presenze extra-alberghi": pd.to_numeric(df[xalb_col], errors="coerce"),
        }
    )
    if out[["Presenze alberghi", "Presenze extra-alberghi"]].isna().any().any():
        raise ValueError("Non-numeric values for 'Presenze' found")
    return out
