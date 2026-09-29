# SPDX-License-Identifier: Apache-2.0
"""
STEP 0 - Download raw data.

Input : server (S3)
Output: Output/raw_data/
        Data are saved exactly as they downloaded.
"""
import logging
from pathlib import Path

from data_preparation.v2.utils.utils import get_s3, get_dataframe, save_computed_dfs
from data_preparation.v2.utils.common import RAW_DIR, check_output_dir

logging.basicConfig(level=logging.INFO)

S3_DATA = [
    "TRENTINO-comuni_Vodafone_2023.geojson",
    "Annuario-TavXIII-per-comune-csv.csv",
    "presenze_Trentino_ISPAT.csv",
    "presenze_Trentino_ISPAT_alb_xalb.csv",
]
# json mappings, inside mapping_ids
MAPPINGS = [
    "mapping_comuni_ISTAT.json",
    "mapping_comuni_into_vodafone_Trento.json",
    "map_comuni_into_apt.json",
]
# dataframes returned by get_dataframe (saved as csv/parquet)
DATAFRAMES = [
    "popolazione_2020_2024",
    "vodafone_attendences",
]


def download_raw_data(out_dir=RAW_DIR, type_format="csv"):
    check_output_dir(out_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in S3_DATA:
        logging.info("Downloading object %s from S3...", name)
        (out_dir / name).write_bytes(get_s3(name).getvalue())
    for name in DATAFRAMES:
            logging.info("Downloading dataframe %s...", name)
            save_computed_dfs(
                {name: get_dataframe(name)},
                local=True,
                type_format=type_format,
                path_saving=out_dir,
            )

    for name in MAPPINGS:
        logging.info("Downloading mapping %s...", name)
        (out_dir / name).write_bytes(get_s3(f"mapping_ids/{name}").getvalue())
    logging.info("Raw data saved in %s", out_dir)


if __name__ == "__main__":
    logging.info("Step 0: download raw data into Output/raw_data")
    dir_out = RAW_DIR
    type_format = "csv"
    download_raw_data(out_dir=dir_out, type_format=type_format)
