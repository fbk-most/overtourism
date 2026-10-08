# SPDX-License-Identifier: Apache-2.0
"""
Yearly update of the phenomenon dataframes (entry point). Same steps of the base build:

    0 download        server (S3 / local folder)     -> Output/data/raw_data/  (+ Output/mapping/)
    1 standardize     raw_data                       -> Output/data/normalized/       <dataset>_update_std
    2 process         normalized (+ mappings)        -> Output/data/data_processed/   <dataset>_update_pr
    3 phenomena       data_processed                 -> Output/data/final_data/
                      appended to the existing phen_* (the update wins on a duplicated DATA + ID_COMUNE)

What is configured, and where:
  - config/settings.yaml          directories, file format, platform (shared with the base build)
  - config/updates/<round>.yaml   which datasets to update (listed / `enabled`), file names, readers,
                                  adapters and their parameters (year, column names...)
A new year with a new layout = a new adapter in utils/adapters/ + a new update yaml.

The final data of the base build (`paths.final` in settings.yaml) must exist, in the same `type_format`.

Usage:
    python -m data_preparation.update_phenomenon_dataframes --config data_preparation/config/updates/update_2025.yaml
    python -m data_preparation.update_phenomenon_dataframes --config ... --skip-download   # raw_data already there
    python -m data_preparation.update_phenomenon_dataframes --config ... --upload          # also log final data to the platform

Each step can also be run on its own, e.g.
    python -m data_preparation.utils.steps.process_update_std_data --config ...
"""

import argparse
import logging
import sys
from pathlib import Path

from data_preparation.utils.config import TYPE_FORMAT, setup_logging
from data_preparation.utils.steps.create_phenomena_df import compute_phenomena
from data_preparation.utils.steps.download_data import download_update_raw_data
from data_preparation.utils.steps.process_update_std_data import process_update_std_data
from data_preparation.utils.steps.standardize_update_raw_data import (
    standardize_update_raw_data,
)
from data_preparation.utils.update.spec import load_config

logger = logging.getLogger(__name__)


def update_pipeline(
    config, type_format=TYPE_FORMAT, local=True, skip_download=False, strict=True
):
    """Runs the whole update and returns the final phenomenon dataframes (existing + update).
    local=False also uploads them to the platform;
    skip_download=True reuses the raw data and the mappings already in Output/;
    strict=False: adapter schema mismatch -> warning instead of error."""
    config = load_config(config)
    logger.info("Update of %s", config.datasets)

    if skip_download:
        logger.info("Step 0/3: download skipped, using the existing raw data")
    else:
        logger.info("Step 0/3: download update raw data")
        download_update_raw_data(config)
    logger.info("Step 1/3: standardize update raw data")
    standardize_update_raw_data(config, type_format=type_format, strict=strict)
    logger.info("Step 2/3: process standardized update data")
    process_update_std_data(config, type_format=type_format)
    logger.info("Step 3/3: compute final phenomena (append to the existing ones)")
    dict_dfs = compute_phenomena(
        type_format=type_format, local=local, datasets=config.datasets
    )
    logger.info("Update finished!")
    return dict_dfs


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Yearly update of the phenomenon dataframes."
    )
    p.add_argument(
        "--config", required=True, type=Path, help="update config (.yaml/.yml/.json)"
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
    p.add_argument(
        "--no-strict",
        action="store_true",
        help="only warn on adapter schema mismatches",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    setup_logging()
    args = _parse_args(argv)
    update_pipeline(
        args.config,
        local=not args.upload,
        skip_download=args.skip_download,
        strict=not args.no_strict,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
