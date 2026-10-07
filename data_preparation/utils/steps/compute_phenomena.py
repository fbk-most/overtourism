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

from data_preparation.utils.config import (
    FINAL_DIR,
    PROCESSED_DIR,
    TYPE_FORMAT,
    setup_logging,
)
from data_preparation.utils.datasets import DATASETS
from data_preparation.utils.io import ensure_dir, read_df, save_computed_dfs

logger = logging.getLogger(__name__)


def compute_presenze_trentino(df_alb, df_extralb, df_vodafone):
    """Daily x comune presences dataframe: ISPAT alb + xalb and vodafone presences."""
    df = df_alb.merge(
        df_extralb[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )

    len_pre = len(df)
    df_mg = df.merge(
        df_vodafone[["DATA", "ID_COMUNE", "presenze"]].rename(
            columns={"presenze": "presenze_vodafone"}
        ),
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )

    if len(df_mg) < len_pre:
        records_lost = len_pre - len(df_mg)
        perc_lost = (records_lost / len_pre) * 100
        missing_dates = set(df["DATA"].dropna()) - set(df_vodafone["DATA"].dropna())

        rows_missing_dates = int(df["DATA"].isin(missing_dates).sum())
        rows_missing_keys = records_lost - rows_missing_dates

        logger.warning(
            "Filtered Vodafone: %d/%d records discarded (%.2f%%).",
            records_lost,
            len_pre,
            perc_lost,
        )
        if missing_dates:
            min_d, max_d = min(missing_dates), max(missing_dates)
            logger.warning(
                "Records lost on dates not covered by Vodafone: %d records across %d days (%s..%s).",
                rows_missing_dates,
                len(missing_dates),
                min_d,
                max_d,
            )
            logger.warning("First day missing: %s | Last: %s", min_d, max_d)
        if rows_missing_keys:
            logger.warning(
                "%d Records lost because of missing ID_COMUNE on common dates.",
                rows_missing_keys,
            )
    return df_mg.sort_values(by=["DATA", "ID_COMUNE"]).reset_index(drop=True)


def compute_phenomena(
    processed_dir=PROCESSED_DIR, out_dir=FINAL_DIR, type_format=TYPE_FORMAT, local=True
):
    """Reads the processed dataframes, computes the phenomena and saves them.
    local=False also uploads the phenomena to the platform."""
    processed_dir = Path(processed_dir)
    ensure_dir(out_dir)

    logger.info("Reading processed data from %s", processed_dir)
    pr = {
        name: read_df(processed_dir, spec.processed_name, type_format)
        for name, spec in DATASETS.items()
    }

    logger.info(
        "## Population and structures dataframes do not require changes and can be saved directly"
    )
    logger.info("## Computing presences phenomenon dataframe")
    presenze_df = compute_presenze_trentino(
        pr["presenze_alb"], pr["presenze_extralb"], pr["vodafone"]
    )

    dict_dfs = {
        "phen_popolazione": pr["popolazione"],
        "phen_strutture": pr["strutture"],
        "phen_presenze": presenze_df,
    }

    save_computed_dfs(
        dict_dfs, local=local, type_format=type_format, path_saving=out_dir
    )
    return dict_dfs


if __name__ == "__main__":
    setup_logging()
    compute_phenomena()
