# SPDX-License-Identifier: Apache-2.0
"""Where raw update files come from (S3 data lake or a local directory) and how they are read.

Readers turn bytes into a RawData(df, meta). To support a new file layout add a function to READERS.
"""

import io
import json
import logging
from pathlib import Path

import pandas as pd

from data_preparation.utils.adapters import RawData
from data_preparation.utils.readers import read_geojson, read_grouped_presenze_tsv

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ fetching
def fetch_bytes(key: str, *, local_dir=None, save_to=None) -> io.BytesIO:
    """Returns the content of `key` (relative to the data-lake prefix, or to `local_dir` if given).
    If `save_to` is set, a copy is stored there under the file's base name."""
    if local_dir is not None:
        buffer = io.BytesIO((Path(local_dir) / key).read_bytes())
    else:
        from data_preparation.utils.remote import get_s3

        buffer = get_s3(key)
    if save_to is not None:
        save_to = Path(save_to)
        save_to.mkdir(parents=True, exist_ok=True)
        (save_to / Path(key).name).write_bytes(buffer.getvalue())
    return buffer


def fetch_json(key: str, *, local_dir=None) -> dict:
    return json.load(fetch_bytes(key, local_dir=local_dir))


def fetch_geojson(key: str, *, local_dir=None, save_to=None):
    return read_geojson(fetch_bytes(key, local_dir=local_dir, save_to=save_to))


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


def read_source(file: str, reader: str, reader_kwargs=None, *, local_dir=None, raw_dir=None) -> RawData:
    """Fetch `file` (saving a raw copy in `raw_dir`) and parse it with the named reader."""
    if reader not in READERS:
        raise KeyError(f"Unknown reader {reader!r}. Available: {sorted(READERS)}")
    logger.info("Fetching %s (reader=%s)", file, reader)
    buffer = fetch_bytes(file, local_dir=local_dir, save_to=raw_dir)
    return READERS[reader](buffer, **(reader_kwargs or {}))
