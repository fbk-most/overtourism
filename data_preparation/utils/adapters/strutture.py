# SPDX-License-Identifier: Apache-2.0
"""Adapters for the strutture ricettive source."""

import pandas as pd

from data_preparation.utils.adapters.base import RawData, register_adapter
from data_preparation.utils.cleaning import remove_unnamed

# 2025 raw column -> name of the base layout (Annuario-TavXIII), in the order of the base file.
STRUTTURE_RAW_RENAMING = {
    "Esercizi alberghieri Numero": "alberghieri strutture",
    "Esercizi alberghieri Letti": "alberghieri posti_letto",
    "Esercizi extralberghieri Numero": "extra alb. Strutture",
    "Esercizi extralberghieri Letti": "extra alb. Posti_letto",
    "Totale Numero": "tot convenzionali strutture",
    "Totale Letti": "tot convenzionali posti_letto",
    "Alloggi turistici Numero": "all. privati numero",
    "Alloggi turistici Letti": "all. privati posti_letto",
    "Alloggi a disposizione Numero": "all.disposizione numero",
    "Alloggi a disposizione Letti": "all. disposizione posti_letto",
}


def _adapt_strutture(
    raw: RawData, *, year: int, comune_col: str, adapter_name: str
) -> pd.DataFrame:
    df = remove_unnamed(raw.df)
    missing = sorted(({comune_col} | set(STRUTTURE_RAW_RENAMING)) - set(df.columns))
    if missing:
        raise ValueError(
            f"{adapter_name}: source layout does not match this handler; missing columns {missing} "
            f"(found: {list(df.columns)}). Add/select a dedicated strutture adapter for this file layout."
        )
    df = df.rename(columns={comune_col: "comune", **STRUTTURE_RAW_RENAMING})
    df = df[["comune", *STRUTTURE_RAW_RENAMING.values()]].copy()
    for c in STRUTTURE_RAW_RENAMING.values():
        df[c] = (
            pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        )  # manage "-"
    df.insert(1, "anno", year)
    return df


@register_adapter("strutture_annuario", kind="strutture")
def strutture_annuario(raw: RawData, *, year: int) -> pd.DataFrame:
    """Default handler for the 2025 ISPAT XLSX layout (including its two-row header)."""
    return _adapt_strutture(
        raw, year=year, comune_col="Comune", adapter_name="strutture_annuario"
    )


@register_adapter("strutture_annuario_2024", kind="strutture")
def strutture_annuario_2024(raw: RawData, *, year: int) -> pd.DataFrame:
    """Handler for the 2024 ODS variant, whose municipality header is `Comuni`."""
    return _adapt_strutture(
        raw, year=year, comune_col="Comuni", adapter_name="strutture_annuario_2024"
    )
