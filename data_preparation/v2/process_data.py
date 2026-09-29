# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 - Processing.

Input : Output/normalized/   (+ mapping json files, read from Output/raw_data)
Output: Output/data_processed/   (popolazione_pr, strutture_pr, vodafone_pr,
                                  presenze_alb_pr, presenze_extralb_pr)

Transformations: ID_COMUNE resolution, filtering, selection of the columns, computation of aggregated columns,
disaggregation of the presences to comune x day (vodafone: areas -> comuni; ISPAT: APT / provincia and
month -> comune and day). 
Every row has a single ID_COMUNE; alb, xalb and vodafone presences.
"""
import logging
from pathlib import Path

import pandas as pd
from data_preparation.v2.utils.utils import (
    save_computed_dfs,
)
from data_preparation.v2.utils.common import (
    RAW_DIR, NORMALIZED_DIR, PROCESSED_DIR, 
    read_df, 
    read_json, 
    normalize_id_comune,
    pad_id_comune,
    resolve_id_comune,
    standard_ordering_cols,
    _remove_provincia,
)
from data_preparation.v2.utils.disaggregation import disaggregate

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


def process_vodafone(df, mapping_vodafone, **disagg_kwargs):
    """vodafone presences: vodafone areas x day -> comune x day.
    disagg_kwargs (e.g. space_weights, space_weight_col) are passed to disaggregate: uniform split if empty."""
    df = _filtering_vodafone_attendences(df)    ## Filtering the attendences on COMUNI & TURISTI
    df["ID_COMUNE"] = df["LOCATION"].map(mapping_vodafone)
    mask = df["LOCATION"] == "SAN GIOVANNI DI FASSA"
    df.loc[mask, "ID_COMUNE"] = pd.Series([[22250]] * mask.sum(), index=df.index[mask], dtype=object)
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"]).apply(normalize_id_comune)  # tuple: hashable for the groupby

    # Sum per (day, vodafone area), then split each area over its comuni
    df = df.groupby(["DATA", "ID_COMUNE"], as_index=False)[VODAFONE_VALUE_COLS].sum()
    df = disaggregate(df, cols=VODAFONE_VALUE_COLS, axis="space", **disagg_kwargs)
    return standard_ordering_cols(df)


def process_presenze_ISPAT(df, mapping_comuni, value_cols, provincia=False, **disagg_kwargs):
    """ISPAT presences (alb: APT, monthly / extralb: provincia, monthly) -> comune x day.
    disagg_kwargs (space / time weights) are passed to disaggregate: uniform split if empty."""
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
    df = df.sort_values(["LOCATION", "DATA"])[["DATA", "ID_COMUNE"] + value_cols]

    # APT / provincia x month -> comune x day
    df = disaggregate(df, cols=value_cols, axis="both", freq_from="M", freq_to="D", **disagg_kwargs)
    return standard_ordering_cols(df)


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

    popolazione_pr = process_popolazione(popolazione_std, mapping_comuni)
    strutture_pr = process_strutture(strutture_std, mapping_comuni)

    ### ---------------------------------- ###
    ## 1. DISAGGREGAZIONE UNIFORME
    ## Le presenze vodafone sono distribuite uniformemente sui comuni
    ## Le presenze ISPAT alberghiere e extra-alberghiere sono distribuite uniformemente sui comuni e sui giorni
    vodafone_pr = process_vodafone(vodafone_std, mapping_vodafone)
    presenze_alb_pr = process_presenze_ISPAT(presenze_alb_std, mapping_apt, PRESENZE_ALB_VALUE_COLS)
    presenze_extralb_pr = process_presenze_ISPAT(
        presenze_extralb_std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True
    )

    ### -------------------------------------------------------------------- ###
    ## 2. VODAFONE PRESENZE
    ## Le presenze vodafone sono distribuite uniformemente sui comuni
    ## Le presenze ISPAT alberghiere e extra-alberghiere sono distribuite seguendo la distribuzione vodafone giornaliera
    # vodafone_pr = process_vodafone(vodafone_std, mapping_vodafone)
    # w = dict(
    #     space_weights=vodafone_pr, space_weight_col="presenze", space_time_freq="M",
    #     time_weights=vodafone_pr, time_weight_col="presenze",
    # )
    # presenze_alb_pr = process_presenze_ISPAT(presenze_alb_std, mapping_apt, PRESENZE_ALB_VALUE_COLS, **w)
    # presenze_extralb_pr = process_presenze_ISPAT(
    #     presenze_extralb_std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True, **w
    # )

    ### -------------------------------------------------------------------- ###
    ## 3. DISAGGREGAZIONE DISTRIBUZIONALE, WRT POSTI LETTO
    ## Le presenze vodafone sono distribuite seguendo la distribuzione annuale dei posti letto totali, sui comuni
    ## Le presenze ISPAT alberghiere e extra-alberghiere seguono rispettivamente i posti letto alberghieri ed extra-alberghieri
    ## Richiede "tot_postiletto_alberghieri" e "tot_postiletto_extralberghieri" in STRUTTURE_VALUE_COLS
    # vodafone_pr = process_vodafone(
    #     vodafone_std, mapping_vodafone,
    #     space_weights=strutture_pr, space_weight_col="tot_postiletto", space_time_freq="Y",
    # )  # space_weights=popolazione_pr, space_weight_col="popolazione", se si volesse per esempio distribuire rispetto alla popolazione
    # presenze_alb_pr = process_presenze_ISPAT(
    #     presenze_alb_std, mapping_apt, PRESENZE_ALB_VALUE_COLS,
    #     space_weights=strutture_pr, space_weight_col="tot_postiletto_alberghieri", space_time_freq="Y",
    #     time_weights=strutture_pr, time_weight_col="tot_postiletto_alberghieri", time_weight_freq="Y",
    # )
    # presenze_extralb_pr = process_presenze_ISPAT(
    #     presenze_extralb_std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True,
    #     space_weights=strutture_pr, space_weight_col="tot_postiletto_extralberghieri", space_time_freq="Y",
    #     time_weights=strutture_pr, time_weight_col="tot_postiletto_extralberghieri", time_weight_freq="Y",
    # )

    dict_processed = {
        "popolazione_pr": popolazione_pr,
        "strutture_pr": strutture_pr,
        "vodafone_pr": vodafone_pr,
        "presenze_alb_pr": presenze_alb_pr,
        "presenze_extralb_pr": presenze_extralb_pr,
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
