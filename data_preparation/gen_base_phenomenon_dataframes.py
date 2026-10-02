# SPDX-License-Identifier: Apache-2.0
"""
STEP 3 - Final phenomenon dataframes.

Input : Output/data_processed/   (already disaggregated to comune x day, see process_data.py)
Output: Output/final_data/   (phen_popolazione, phen_strutture, phen_presenze)
        or upload to the platform

Each phenomenon dataframe is typically contains:
  - DATA: YYYY for yearly data, YYYY-MM-DD for daily data
  - ID_COMUNE: zero-padded ISTAT code (e.g. 22001 -> "022001")
plus the phenomenon's value columns

Relevant for the indicators:
  "tasso-ricettivita", "indice-turisticita", "indice-stagionalita",
  "indice-ospitalita", "indice-turismo-sommerso"
"""

import logging
from pathlib import Path
from data_preparation.utils.utils import save_computed_dfs
from data_preparation.utils.common import (
    PROCESSED_DIR,
    FINAL_DIR,
    read_df,
    check_output_dir,
)

logging.basicConfig(level=logging.INFO)


## COMPUTATION
## The processed presences are already split to comune x day (step 2):
## here alb, xalb and vodafone presences are merged into a single phenomenon dataframe.
def compute_presenze_trentino(df_alb, df_extralb, df_vodafone):
    """Daily x comune presences dataframe: ISPAT alb + xalb and vodafone presences."""
    df = df_alb.merge(
        df_extralb[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    df = df.merge(
        df_vodafone[["DATA", "ID_COMUNE", "presenze"]].rename(
            columns={"presenze": "presenze_vodafone"}
        ),
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    return df.sort_values(by=["DATA", "ID_COMUNE"]).reset_index(drop=True)


def calculate_phenomena(
    popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb
):
    """Builds the final phenomenon dataframes from the processed ones.
    Returns a dict with keys "phen_popolazione", "phen_strutture", "phen_presenze".
    """
    logging.info("## Computing presences phenomenon dataframe")
    presenze_df = compute_presenze_trentino(
        presenze_df_alb, presenze_df_extralb, vodafone_df
    )

    return {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_df,
        "phen_presenze": presenze_df,
    }


## STEP computation of phenomena
def main_compute_phenomena_dfs(
    processed_dir=PROCESSED_DIR, out_dir=FINAL_DIR, type_format="csv", local=True
):
    """Main orchestrator,
    local defines if to upload the phenomena or save them locally in out_dir,
    local=False uploads the phenomena to the platform"""

    processed_dir = Path(processed_dir)
    check_output_dir(out_dir)

    logging.info("Reading processed data from %s", processed_dir)
    read = lambda name: read_df(processed_dir, name, type_format)
    popolazione_df = read("popolazione_pr")
    strutture_df = read("strutture_pr")
    vodafone_df = read("vodafone_pr")
    presenze_df_alb = read("presenze_alb_pr")
    presenze_df_extralb = read("presenze_extralb_pr")

    logging.info("## Computing phenomenon dataframes")
    dict_dfs = calculate_phenomena(
        popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb
    )

    logging.info("## Saving phenomenon dataframes...")
    save_computed_dfs(
        dict_dfs,
        local=local,
        type_format=type_format,
        path_saving=out_dir,
    )
    return dict_dfs


if __name__ == "__main__":
    logging.info("Step 3: Output/data_processed -> Output/final_data")
    dir_in = PROCESSED_DIR
    dir_out = FINAL_DIR
    type_format = "csv"
    local = True
    main_compute_phenomena_dfs(dir_in, dir_out, type_format, local=local)
