# SPDX-License-Identifier: Apache-2.0
"""
Shared paths helper functions for the data preparation pipeline.
"""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
from unidecode import unidecode
import logging 
logging.basicConfig(level=logging.INFO)

OUTPUT_DIR = Path(__file__).parent.parent / "Output"
RAW_DIR = OUTPUT_DIR / "data" / "raw_data"
NORMALIZED_DIR = OUTPUT_DIR / "data" / "normalized"
PROCESSED_DIR = OUTPUT_DIR / "data" / "data_processed"
FINAL_DIR = OUTPUT_DIR / "data" / "final_data"


# Explicit overrides for comuni whose official Italian name differs from
# a naive "before the dash" split of the bilingual name in the source CSV.
COMUNE_NAME_OVERRIDES = {
    "CAMPITELLO DI FASSA-CIAMPEDEL": "CAMPITELLO DI FASSA",
    "CAMPODENNO": "CAMPODENNO",  # no dash present, check exact spelling/accents in mapping
    "CANAL SAN BOVO": "CANAL SAN BOVO",
    "CANAZEI-CIANACEI": "CANAZEI",
    "FIEROZZO-VLAROTZ": "FIEROZZO",
    "FRASSILONGO-GARAIT": "FRASSILONGO",
    "LUSERNA-LUSERN": "LUSERNA",
    "MAZZIN-MAZIN": "MAZZIN",
    "MOENA-MOENA": "MOENA",
    "PALU DEL FERSINA-PALAI EN BERSNTOL": "PALU DEL FERSINA",
    "SAN GIOVANNI DI FASSA-SEN JAN": "SAN GIOVANNI DI FASSA",
    "SORAGA DI FASSA-SORAGA": "SORAGA DI FASSA",
}


## UTILS FUNCTIONS
## Some functions for decoding / padding / cleaning

def customize_unidecode(x):
    """
    Convert the input string, removing accents, converting to uppercase, and stripping whitespace.
    """
    if x.endswith("'"):  # removes also trailing apostrophe if present
        x = x.removesuffix("'")
    return unidecode(x.strip().upper()).replace("0", "-")


def pad_id_comune(series, width=6):
    """Zero-pad an ID_COMUNE column to `width` digits (e.g. 22001 -> '022001').

    Missing / unmapped values (NaN) are left untouched. Works regardless of
    whether the column arrives as int, float (common when NaNs are present),
    or string dtype.
    Works seamlessly for scalars (int, float, str, NaN) and lists of IDs.
    """
    def _pad(x):
        if isinstance(x, list):
            return [_pad(i) for i in x]
        
        if pd.isna(x):
            return x
        return str(int(x)).zfill(width)

    return series.apply(_pad)


def _remove_provincia(df, comune_col="comune", upper=False):
    """Drop rows whose comune starts with 'PROVINCIA', logging what gets removed."""
    df = df.copy()
    series = df[comune_col].str.upper() if upper else df[comune_col]
    mask = series.str.startswith("PROVINCIA")
    if mask.any():
        logging.info(
            f"Comune {df.loc[mask, comune_col].unique()} is a PROVINCIA, removing it from the analysis"
        )
        df = df[~mask]
    return df


def _to_data_location(df, date_col, drop_cols=None):
    """Standardize a phenomenon dataframe to DATA/LOCATION column naming.

    date_col: name of the column holding the time dimension (e.g. "anno" or "date").
    drop_cols: optional columns to drop before returning (e.g. a redundant "anno"
    column once the daily "date" column is promoted to DATA).
    """
    df = df.drop(columns=drop_cols) if drop_cols else df
    return df.rename(columns={date_col: "DATA", "comune": "LOCATION"})


def resolve_id_comune(name, mapping_comuni, overrides=COMUNE_NAME_OVERRIDES):
    """Map a comune name to its ISTAT ID, falling back to the bilingual-name overrides."""
    id_comune = mapping_comuni.get(name)
    if id_comune is None and name in overrides:
        id_comune = mapping_comuni.get(overrides[name])
    return id_comune


def standard_ordering_cols(df):
    existing_first = [col for col in ["DATA", "ID_COMUNE"] if col in df.columns]  # , "ID_COMUNE"
    remaining = [col for col in df.columns if col not in  ["DATA", "ID_COMUNE"]]
    return df[existing_first + remaining]

def normalize_id_comune(x):
    """Canonical hashable form of ID_COMUNE: lists, tuples, arrays (parquet) and
    strings like "['022001', '022002']" (csv) all become a sorted tuple;
    scalars are left untouched."""
    if isinstance(x, str) and x.strip().startswith("["):
        x = ast.literal_eval(x)
    if isinstance(x, (list, tuple, np.ndarray)):
        return tuple(sorted(x))
    return x


def check_output_dir(path):
    if "index_data_v2" in Path(path).resolve().parts:
        raise ValueError(f"Refusing to write inside index_data_v2: {path}")


def read_df(path, name, type_format="csv", parse_ids=False):
    """Reads path/name in type_format format. With parse_ids=True, ID_COMUNE is
    brought back to its canonical form (lists are serialized as strings in csv)."""
    file = Path(path) / f"{name}.{type_format}"
    if not file.exists():
        raise FileNotFoundError(f"{file} not found: run the previous step (download raw data)")
    if type_format == "csv":
        df = pd.read_csv(file, dtype={"ID_COMUNE": str})
    else:
        df = pd.read_parquet(file)
    if parse_ids and "ID_COMUNE" in df.columns:
        df["ID_COMUNE"] = df["ID_COMUNE"].apply(normalize_id_comune)
    return df


def _remove_unnamed(df):
    """Removes unnamed from header.
    If the columns are already flat strings (as in the reconstructed TSVs), this is a no-op and we leave them untouched.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df.copy()

    top = pd.Series([c[0] for c in df.columns])
    top = top.where(~top.astype(str).str.startswith("Unnamed"), pd.NA).ffill()
    bottom = pd.Series([c[1] for c in df.columns])

    df = df.copy()
    df.columns = [
        str(t).strip() if str(b).startswith("Unnamed") or pd.isna(b)
        else f"{str(t).strip()} {str(b).strip()}"
        for t, b in zip(top, bottom)
    ]
    return df

def _read_grouped_presenze_tsv(data_source, sep: str = "\t") -> pd.DataFrame:
    """
    This function reshapes the grouped header into flat columns, like: Mese, Esercizi alberghieri Italiani, Esercizi alberghieri Stranieri, ...
    """
    if hasattr(data_source, "read"):
        data = data_source.getvalue().decode("utf-8")
        lines = [ln.rstrip("\n") for ln in data.splitlines() if ln.strip()]
        path_desc = "buffer"
    else:
        path = str(data_source)
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        path_desc = path
    if len(lines) < 2:
        raise ValueError(f"File troppo corto per header a 2 righe: {path_desc}")
    first = [c.strip() for c in lines[0].split(sep)]
    second = [c.strip() for c in lines[1].split(sep)]
    groups = [c for c in first if c and c.lower() != "mese"]
    if not groups:
        raise ValueError(f"Header della prima riga non riconosciuto: {first}")
    names = ["Mese"]
    for group in groups:
        names.extend([f"{group} Italiani", f"{group} Stranieri", f"{group} Totale"])
    if len(names) != len(second) + 1:
        # Fallback: if the file is already sufficiently aligned, read it with a
        # MultiIndex-like structure instead of manually reconstructing names.
        if hasattr(data_source, "read"):
            return pd.read_csv(data_source, sep=sep, header=[0, 1], dtype=str)
        return pd.read_csv(path_desc, sep=sep, header=[0, 1], dtype=str)

    if hasattr(data_source, "read"):
        return pd.read_csv(
            pd.io.common.StringIO(data),
            sep=sep,
            header=None,
            names=names,
            skiprows=2,
            dtype=str,
        )

    return pd.read_csv(
        path_desc,
        sep=sep,
        header=None,
        names=names,
        skiprows=2,
        dtype=str,
    )

def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

