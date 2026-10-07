# SPDX-License-Identifier: Apache-2.0
"""Low-level file readers shared by the base pipeline and the update pipeline."""

import pandas as pd

from data_preparation.utils.cleaning import grouped_presenze_columns


def read_geojson(source):
    """GeoDataFrame from a path or file-like object (geopandas imported lazily)."""
    import geopandas as gpd

    return gpd.read_file(source)


def read_grouped_presenze_tsv(data_source, sep: str = "\t") -> pd.DataFrame:
    """Reshapes the 2-row grouped header into flat columns
    (Mese, '<group> Italiani', '<group> Stranieri', '<group> Totale', ...).
    `data_source` is a path or an in-memory buffer (BytesIO)."""
    is_buffer = hasattr(data_source, "read")
    if is_buffer:
        data = data_source.getvalue().decode("utf-8")
        lines = [ln.rstrip("\n") for ln in data.splitlines() if ln.strip()]
        path_desc = "buffer"
    else:
        path_desc = str(data_source)
        with open(path_desc, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"File too short for a 2-row header: {path_desc}")
    first = [c.strip() for c in lines[0].split(sep)]
    second = [c.strip() for c in lines[1].split(sep)]
    groups = [c for c in first if c and c.lower() != "mese"]
    if not groups:
        raise ValueError(f"First header row not recognised: {first}")
    names = grouped_presenze_columns(groups)

    if len(names) != len(second) + 1:
        # Fallback: the file is already aligned, read it with a 2-level header.
        return pd.read_csv(
            data_source if is_buffer else path_desc, sep=sep, header=[0, 1], dtype=str
        )

    source = pd.io.common.StringIO(data) if is_buffer else path_desc
    return pd.read_csv(source, sep=sep, header=None, names=names, skiprows=2, dtype=str)
