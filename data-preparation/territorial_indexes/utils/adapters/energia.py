# SPDX-License-Identifier: Apache-2.0
"""Adapter for the energy sources (electricity and gas withdrawals), yearly update.

ASSUMPTION (see METHODOLOGY.md, `phen_consumption`): the files of the update have the same layout as the category files of the
base build (`Energia/<ee_prelievi|gas_prelievi>/<49_3|55_1|56_1|93_1|96>.csv`: semicolon-delimited, one row per
year x comune x usage category, one column per month). They are read with the reader `energy_csv`, which already
returns the standard layout (DATA = year, LOCATION, codice_utilizzo, gennaio..dicembre); the adapter checks it.
If the provider changes the layout, write another adapter (and reader) and reference it in the update yaml.
"""

import pandas as pd

from utils.adapters.base import RawData, register_adapter

ENERGY_COLUMNS = (
    "DATA",
    "LOCATION",
    "codice_utilizzo",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


@register_adapter("energia_categorie", kind="energia")
def energia_categorie(raw: RawData) -> pd.DataFrame:
    """Energy category file already in the standard layout (read with `energy_csv`): returned unchanged."""
    missing = [c for c in ENERGY_COLUMNS if c not in raw.df.columns]
    if missing:
        raise ValueError(
            f"energia_categorie: source layout does not match; missing columns {missing} "
            f"(found: {list(raw.df.columns)}). Read the file with reader 'energy_csv' or write a dedicated adapter."
        )
    return raw.df
