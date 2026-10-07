# SPDX-License-Identifier: Apache-2.0
"""
STEP 3 - Final phenomenon dataframes.

Input : Output/data/data_processed/   (already disaggregated to comune x day, see process_std_data.py)
Output: Output/data/final_data/       (phen_popolazione, phen_strutture, phen_presenze)
        and, with local=False, the platform

Each phenomenon dataframe contains:
  - DATA: YYYY for yearly data, YYYY-MM-DD for daily data
  - ID_COMUNE: zero-padded ISTAT code (e.g. 22001 -> "022001")
plus the phenomenon's value columns.
"""

import logging
from pathlib import Path

from data_preparation.utils.config import FINAL_DIR, PROCESSED_DIR, TYPE_FORMAT
from data_preparation.utils.datasets import DATASETS
from data_preparation.utils.io import ensure_dir, read_df, save_computed_dfs
from data_preparation.utils.phenomena import calculate_phenomena

logger = logging.getLogger(__name__)


def compute_phenomena(processed_dir=PROCESSED_DIR, out_dir=FINAL_DIR, type_format=TYPE_FORMAT, local=True):
    """Reads the processed dataframes, computes the phenomena and saves them.
    local=False also uploads the phenomena to the platform."""
    processed_dir = Path(processed_dir)
    ensure_dir(out_dir)

    logger.info("Reading processed data from %s", processed_dir)
    pr = {
        name: read_df(processed_dir, spec.processed_name, type_format)
        for name, spec in DATASETS.items()
    }

    dict_dfs = calculate_phenomena(
        pr["popolazione"], pr["strutture"], pr["vodafone"], pr["presenze_alb"], pr["presenze_extralb"]
    )
    save_computed_dfs(dict_dfs, local=local, type_format=type_format, path_saving=out_dir)
    return dict_dfs
