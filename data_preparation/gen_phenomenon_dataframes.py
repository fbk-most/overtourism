# SPDX-License-Identifier: Apache-2.0
"""
Base build of the phenomenon dataframes, from scratch (entry point). Runs ALL the steps:

    0 download        server (S3 / platform)       -> Output/data/raw_data/
    1 standardize     raw_data                     -> Output/data/normalized/
    2 process         normalized (+ mappings)      -> Output/data/data_processed/
    3 phenomena       data_processed               -> Output/data/final_data/
                      (phen_popolazione, phen_strutture, phen_presenze)

Every step reads the output of the previous one. Directories, file format (`type_format`, parquet by
default) and platform settings are in config/settings.yaml.

Usage:
    python -m data_preparation.gen_base_phenomenon_dataframes                  # all steps
    python -m data_preparation.gen_base_phenomenon_dataframes --skip-download  # raw_data already there
    python -m data_preparation.gen_base_phenomenon_dataframes --upload         # also log final data to the platform

Each step can also be run on its own, see utils/steps/.
"""

import argparse
import logging

from data_preparation.utils.config import TYPE_FORMAT, setup_logging
from data_preparation.utils.steps.create_phenomena_df import compute_phenomena
from data_preparation.utils.steps.download_data import download_raw_base_data
from data_preparation.utils.steps.process_std_data import process_data
from data_preparation.utils.steps.standardize_raw_data import standardize_raw_data

logger = logging.getLogger(__name__)


def main_compute_phenomena_dfs(
    type_format=TYPE_FORMAT, local=True, skip_download=False
):
    """Runs the whole base pipeline and returns the final phenomenon dataframes.
    local=False also uploads the final dataframes to the platform;
    skip_download=True reuses the raw data already in Output/data/raw_data."""
    if skip_download:
        logger.info("Step 0/3: download skipped, using the existing raw data")
    else:
        logger.info("Step 0/3: download raw data")
        download_raw_base_data(type_format=type_format)
    logger.info("Step 1/3: standardize raw data")
    standardize_raw_data(type_format=type_format)
    logger.info("Step 2/3: process standardized data")
    process_data(type_format=type_format)
    logger.info("Step 3/3: compute final phenomena")
    dict_dfs = compute_phenomena(type_format=type_format, local=local)
    logger.info("Pipeline finished!")
    return dict_dfs


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Base build of the phenomenon dataframes (all steps)."
    )
    p.add_argument(
        "--skip-download",
        action="store_true",
        help="reuse the raw data already downloaded",
    )
    p.add_argument(
        "--upload",
        action="store_true",
        help="log the final phenomena to the platform too",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    setup_logging()
    args = _parse_args()
    main_compute_phenomena_dfs(local=not args.upload, skip_download=args.skip_download)
