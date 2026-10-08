# SPDX-License-Identifier: Apache-2.0
"""How the raw update files (already downloaded in raw_data, see steps/download_data.py) are read.

Readers turn bytes into a RawData(df, meta). To support a new file layout add a function to READERS.
"""

import io
import logging
from pathlib import Path

import pandas as pd

from data_preparation.utils.adapters import RawData
from data_preparation.utils.readers import read_grouped_presenze_tsv

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ readers
def read_csv(buffer, **kwargs) -> RawData:
    return RawData(pd.read_csv(buffer, **kwargs))


def read_excel(buffer, **kwargs) -> RawData:
    """.xlsx / .ods (pass engine='odf' for ods); kwargs go to pandas.read_excel (header, sheet_name...)."""
    return RawData(pd.read_excel(buffer, **kwargs))


def read_ispat_apt_tsv(buffer, sep="\t", skiprows=2) -> RawData:
    """ISPAT APT-level TSV: 2-row header, no header parsing; first row (the APT names) goes to meta['apts']."""
    df = pd.read_csv(buffer, sep=sep, header=None, skiprows=skiprows, dtype=str)
    apts = [x.strip() for x in buffer.getvalue().decode("utf-8").splitlines()[0].split(sep)]
    return RawData(df, {"apts": apts})


def read_ispat_grouped_tsv(buffer, sep="\t") -> RawData:
    """ISPAT TSV with grouped header, flattened to 'Mese', '<group> Italiani/Stranieri/Totale'."""
    return RawData(read_grouped_presenze_tsv(buffer, sep=sep))


READERS = {
    "csv": read_csv,
    "excel": read_excel,
    "ispat_apt_tsv": read_ispat_apt_tsv,
    "ispat_grouped_tsv": read_ispat_grouped_tsv,
}


def read_source(file: str, reader: str, reader_kwargs=None, *, raw_dir) -> RawData:
    """Parses `file` (already downloaded in `raw_dir`) with the named reader."""
    if reader not in READERS:
        raise KeyError(f"Unknown reader {reader!r}. Available: {sorted(READERS)}")
    path = Path(raw_dir) / Path(file).name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run the download step first")
    logger.info("Reading %s (reader=%s)", path, reader)
    return READERS[reader](io.BytesIO(path.read_bytes()), **(reader_kwargs or {}))
