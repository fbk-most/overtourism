# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 - Processing.

Input : Output/normalized/   (+ mapping json files, read from Output/raw_data)
Output: Output/data_processed/   (popolazione_pr, strutture_pr, vodafone_pr,
                                  presenze_alb_pr, presenze_extralb_pr)

Transformations: ID_COMUNE resolution, filtering, selection of the columns, computation of aggregated columns.
"""
import logging
from pathlib import Path

import pandas as pd

from data_preparation.v2.utils.utils import (
    pad_id_comune,
    resolve_id_comune,
    standard_ordering_cols,
    _remove_provincia,
    save_computed_dfs
)
from data_preparation.v2.common import (
    RAW_DIR, NORMALIZED_DIR, PROCESSED_DIR, read_df, read_json,
)

logging.basicConfig(level=logging.INFO)

## CONSTANT VARIABLES
STRUTTURE_VALUE_COLS = [
    "tot_postiletto_non_conv",
    "tot_postiletto",
    "tot_strutture_non_conv",
    "tot_strutture",
]
VODAFONE_VALUE_COLS = ["presenze"]
POPOLAZIONE_VALUE_COLS = ["popolazione"]
PRESENZE_ALB_VALUE_COLS = ["presenze_alb"]
PRESENZE_XALB_VALUE_COLS = ["presenze_xalb"]

RENAMING_STRUTTURE = {
    "alberghieri posti_letto": "tot_postiletto_alberghieri",
    "extra alb. Posti_letto": "tot_postiletto_extralberghieri",

    "alberghieri strutture": "tot_strutture_alberghiere",
    "extra alb. Strutture": "tot_strutture_extralberghiere",

    "all. privati numero": "tot_strutture_non_conv",
    "all. privati posti_letto": "tot_postiletto_non_conv",

    "tot convenzionali posti_letto": "tot_postiletto_conv",
    "tot convenzionali strutture": "tot_strutture_conv",
}


## FILTERING HELPERS
def _filtering_strutture(df, min_year, year_col="DATA"):
    """Excludes years pre-2020, geography changes for municipalities aggregations"""
    return df[df[year_col] > min_year].copy()


def _filtering_vodafone_attendences(df):
    """Filtering presences on tourists and municipalities"""
    return df[
        (df["userProfile"] == "TOURIST")
        & (df["locType"] == "TN_MKT_AL_3")
    ].copy()


## PROCESSING FUNCTIONS
def process_popolazione(df, mapping_comuni):
    df["ID_COMUNE"] = df["LOCATION"].apply(lambda x: resolve_id_comune(x, mapping_comuni))
    df = _remove_provincia(df, comune_col="LOCATION")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + POPOLAZIONE_VALUE_COLS])


def process_strutture(df, mapping_comuni):
    df = _filtering_strutture(df, 2019)
    df = _remove_provincia(df, comune_col="LOCATION")
    df = df.rename(columns=RENAMING_STRUTTURE)

    # Compute total as the sum of CONV and NON CONV
    df["tot_strutture"] = df["tot_strutture_conv"] + df["tot_strutture_non_conv"]
    df["tot_postiletto"] = df["tot_postiletto_conv"] + df["tot_postiletto_non_conv"]

    # Set ID_COMUNE (resolving the bilingual overrides)
    df["ID_COMUNE"] = df["LOCATION"].apply(lambda x: resolve_id_comune(x, mapping_comuni))
    missing = df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique()
    if len(missing) > 0:
        logging.warning(
            f"[process_strutture] Nessun ID_COMUNE trovato (anche con overrides) per: {sorted(missing)}"
        )

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + STRUTTURE_VALUE_COLS])


def process_vodafone(df, mapping_vodafone):
    """vodafone presences, granularity: vodafone aggregations, daily"""
    df = _filtering_vodafone_attendences(df)    ## Filtering the attendences on COMUNI & TURISTI 
    df["ID_COMUNE"] = df["LOCATION"].map(mapping_vodafone)
    mask = df["LOCATION"] == "SAN GIOVANNI DI FASSA"
    df.loc[mask, "ID_COMUNE"] = pd.Series([[22250]] * mask.sum(), index=df.index[mask], dtype=object)
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + VODAFONE_VALUE_COLS])


def process_presenze_ISPAT(df, mapping_comuni, value_cols, provincia=False):
    """ISPAT presences (alb: APT, monthly / extralb: provincia, monthly)"""
    df.drop(columns=["Anno", "Mese"], inplace=True)
    if provincia:
        df["LOCATION"] = "PROVINCIA"
        df["ID_COMUNE"] = [list(mapping_comuni.values())] * len(df)
    else:
        df["ID_COMUNE"] = df["LOCATION"].map(mapping_comuni).apply(
            lambda x: [int(i) for i in x] if isinstance(x, list) else x
        )
        df = _remove_provincia(df, "LOCATION", True)
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["LOCATION", "DATA"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + value_cols])


## Processing step
def process_data(normalized_dir=NORMALIZED_DIR, mapping_dir=RAW_DIR, out_dir=PROCESSED_DIR, type_format="csv"):
    normalized_dir, mapping_dir = Path(normalized_dir), Path(mapping_dir)

    logging.info("Reading standardized data from %s", normalized_dir)
    popolazione_std = read_df(normalized_dir, "popolazione_std", type_format)
    strutture_std = read_df(normalized_dir, "strutture_std", type_format)
    vodafone_std = read_df(normalized_dir, "vodafone_std", type_format)
    presenze_alb_std = read_df(normalized_dir, "presenze_alb_std", type_format)
    presenze_extralb_std = read_df(normalized_dir, "presenze_extralb_std", type_format)

    mapping_comuni = read_json(mapping_dir / "mapping_comuni_ISTAT.json")
    mapping_vodafone = read_json(mapping_dir / "mapping_comuni_into_vodafone_Trento.json")
    mapping_apt = read_json(mapping_dir / "map_comuni_into_apt.json")

    dict_processed = {
        "popolazione_pr": process_popolazione(popolazione_std, mapping_comuni),
        "strutture_pr": process_strutture(strutture_std, mapping_comuni),
        "vodafone_pr": process_vodafone(vodafone_std, mapping_vodafone),
        "presenze_alb_pr": process_presenze_ISPAT(presenze_alb_std, mapping_apt, PRESENZE_ALB_VALUE_COLS),
        "presenze_extralb_pr": process_presenze_ISPAT(
            presenze_extralb_std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True
        ),
    }

    save_computed_dfs(
            dict_processed,
            local=True,
            type_format=type_format,
            path_saving=out_dir,
        )    
    logging.info("Processed data saved in %s", out_dir)
    return dict_processed


if __name__ == "__main__":
    logging.info("Step 2: Output/normalized -> Output/data_processed")
    normalized_dir= NORMALIZED_DIR
    mapping_dir= RAW_DIR
    out_dir= PROCESSED_DIR
    type_format= "csv"
    process_data(normalized_dir, mapping_dir, out_dir, type_format)
