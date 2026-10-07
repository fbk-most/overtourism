# SPDX-License-Identifier: Apache-2.0
"""
STEP 0 - Download raw data.

Input : server (S3 / platform)
Output: Output/data/raw_data/   (data saved exactly as downloaded)
        Output/mapping/         (the json mappings, shared with the update)
"""

import logging

from data_preparation.utils.config import (
    MAPPING_DIR,
    RAW_DIR,
    REFERENCES,
    TYPE_FORMAT,
    setup_logging,
)
from data_preparation.utils.io import ensure_dir, save_computed_dfs

logger = logging.getLogger(__name__)

S3_DATA = [
    "Annuario-TavXIII-per-comune-csv.csv",
    "presenze_Trentino_ISPAT.csv",
    "presenze_Trentino_ISPAT_alb_xalb.csv",
]
# dataframes returned by get_dataframe (saved as csv/parquet)
DATAFRAMES = [
    "popolazione_2020_2024",
    "vodafone_attendences",
]


def download_raw_data(
    out_dir=RAW_DIR, type_format=TYPE_FORMAT, mapping_dir=MAPPING_DIR
):
    from data_preparation.utils.remote import get_dataframe, get_s3

    out_dir = ensure_dir(out_dir)
    mapping_dir = ensure_dir(mapping_dir)

    for name in S3_DATA:
        logger.info("Downloading object %s from S3...", name)
        (out_dir / name).write_bytes(get_s3(name).getvalue())

    for name in DATAFRAMES:
        logger.info("Downloading dataframe %s...", name)
        save_computed_dfs(
            {name: get_dataframe(name)},
            local=True,
            type_format=type_format,
            path_saving=out_dir,
        )
    for key in (
        REFERENCES["mapping_comuni"],
        REFERENCES["mapping_vodafone"],
        REFERENCES["mapping_apt"],
        REFERENCES["geojson"],
    ):
        logger.info("Downloading mapping %s...", key)
        (mapping_dir / key.split("/")[-1]).write_bytes(get_s3(key).getvalue())
    logger.info("Raw data saved in %s, mappings in %s", out_dir, mapping_dir)


if __name__ == "__main__":
    setup_logging()
    download_raw_data()
