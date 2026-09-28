# SPDX-License-Identifier: Apache-2.0
"""
Shared paths and I/O helpers for the data preparation pipeline.
"""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path(__file__).parent / "Output"
RAW_DIR = OUTPUT_DIR / "raw_data"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"
PROCESSED_DIR = OUTPUT_DIR / "data_processed"
FINAL_DIR = OUTPUT_DIR / "final_data"


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


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

