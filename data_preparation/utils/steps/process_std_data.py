# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 - Processing.

Input : Output/data/normalized/   (+ mapping json files, read from Output/mapping)
Output: Output/data/data_processed/   (popolazione_pr, strutture_pr, vodafone_pr,
                                       presenze_alb_pr, presenze_extralb_pr)

Transformations: ID_COMUNE resolution, filtering, selection of the columns, computation of
aggregated columns, disaggregation of the presences to comune x day (vodafone: areas -> comuni;
ISPAT: APT / provincia and month -> comune and day). Every row has a single ID_COMUNE.
"""

import logging
from pathlib import Path

import pandas as pd

from data_preparation.utils.cleaning import (
    ids_to_int,
    normalize_id_comune,
    pad_id_comune,
    remove_provincia,
    resolve_id_comune,
    standard_ordering_cols,
)
from data_preparation.utils.config import (
    MAPPING_DIR,
    NORMALIZED_DIR,
    PROCESSED_DIR,
    TYPE_FORMAT,
    MAPPING_FILES,
    setup_logging,
)
from data_preparation.utils.datasets import (  # noqa: F401  (re-exported for convenience)
    DATASETS,
    POPOLAZIONE_VALUE_COLS,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_XALB_VALUE_COLS,
    STRUTTURE_VALUE_COLS,
    VODAFONE_VALUE_COLS,
)
from data_preparation.utils.disaggregation import disaggregate
from data_preparation.utils.io import read_df, read_json, save_computed_dfs

logger = logging.getLogger(__name__)


def _filtering_strutture(df, min_year, year_col="DATA"):
    """Excludes years pre-2020, geography changes for municipalities aggregations"""
    return df[df[year_col] > min_year].copy()


def _filtering_vodafone_attendences(df):
    """Filtering presences on tourists and municipalities"""
    return df[
        (df["userProfile"] == "TOURIST") & (df["locType"] == "TN_MKT_AL_3")
    ].copy()


def process_popolazione(df, mapping_comuni):
    df["ID_COMUNE"] = df["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    df = remove_provincia(df, comune_col="LOCATION")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + POPOLAZIONE_VALUE_COLS])


def process_strutture(df, mapping_comuni):
    df = _filtering_strutture(df, 2019)
    df = remove_provincia(df, comune_col="LOCATION")

    # CONV = alberghieri + extralberghieri (from the raw components, not from the raw CONV totals)
    df["tot_strutture_conv"] = df["alberghieri strutture"] + df["extra alb. Strutture"]
    df["tot_postiletto_conv"] = (
        df["alberghieri posti_letto"] + df["extra alb. Posti_letto"]
    )

    df["tot_strutture_non_conv"] = (
        df["all. privati numero"] + df["all.disposizione numero"]
    )
    df["tot_postiletto_non_conv"] = (
        df["all. privati posti_letto"] + df["all. disposizione posti_letto"]
    )

    # Compute total as the sum of CONV and NON CONV
    df["tot_strutture"] = df["tot_strutture_conv"] + df["tot_strutture_non_conv"]
    df["tot_postiletto"] = df["tot_postiletto_conv"] + df["tot_postiletto_non_conv"]

    # Set ID_COMUNE (resolving the bilingual overrides)
    df["ID_COMUNE"] = df["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    missing = df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique()
    if len(missing) > 0:
        logger.warning(
            "[process_strutture] No ID_COMUNE found (even with overrides) for: %s",
            sorted(missing),
        )

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + STRUTTURE_VALUE_COLS])


def process_vodafone(df, mapping_vodafone, **disagg_kwargs):
    """vodafone presences: vodafone areas x day -> comune x day.
    disagg_kwargs (e.g. space_weights, space_weight_col) are passed to disaggregate: uniform split if empty.
    """
    df = _filtering_vodafone_attendences(df)  # only COMUNI & TURISTI
    df["ID_COMUNE"] = df["LOCATION"].map(mapping_vodafone)
    mask = df["LOCATION"] == "SAN GIOVANNI DI FASSA"
    df.loc[mask, "ID_COMUNE"] = pd.Series(
        [[22250]] * mask.sum(), index=df.index[mask], dtype=object
    )
    if df["ID_COMUNE"].isna().any():
        locations = sorted(
            df.loc[df["ID_COMUNE"].isna(), "LOCATION"].dropna().unique().tolist()
        )
        logger.warning(
            "[process_vodafone] %d rows Vodafone (%d aree) with no mapping ID_COMUNE; "
            "rows will be excluded by groupby: %s",
            int(df["ID_COMUNE"].isna().sum()),
            len(locations),
            locations,
        )
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"]).apply(
        normalize_id_comune
    )  # hashable

    # Sum per (day, vodafone area), then split each area over its comuni
    df = df.groupby(["DATA", "ID_COMUNE"], as_index=False)[VODAFONE_VALUE_COLS].sum()
    df = disaggregate(df, cols=VODAFONE_VALUE_COLS, axis="space", **disagg_kwargs)
    return standard_ordering_cols(df)


def process_presenze_ISPAT(
    df, mapping_comuni, value_cols, provincia=False, **disagg_kwargs
):
    """ISPAT presences (alb: APT, monthly / extralb: provincia, monthly) -> comune x day.
    disagg_kwargs (space / time weights) are passed to disaggregate: uniform split if empty.
    """
    df.drop(columns=["Anno", "Mese"], inplace=True)
    if provincia:
        df["LOCATION"] = "PROVINCIA"
        df["ID_COMUNE"] = [list(mapping_comuni.values())] * len(df)
    else:
        df["ID_COMUNE"] = df["LOCATION"].map(mapping_comuni).apply(ids_to_int)
        df = remove_provincia(df, "LOCATION", True)
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["LOCATION", "DATA"])[["DATA", "ID_COMUNE"] + value_cols]

    # APT / provincia x month -> comune x day
    df = disaggregate(
        df, cols=value_cols, axis="both", freq_from="M", freq_to="D", **disagg_kwargs
    )
    return standard_ordering_cols(df)


def load_mappings(mapping_dir):
    mapping_dir = Path(mapping_dir)
    return {key: read_json(mapping_dir / fname) for key, fname in MAPPING_FILES.items()}


def process_data(
    normalized_dir=NORMALIZED_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=PROCESSED_DIR,
    type_format=TYPE_FORMAT,
):
    normalized_dir = Path(normalized_dir)

    logger.info("Reading standardized data from %s", normalized_dir)
    std = {
        name: read_df(normalized_dir, DATASETS[name].std_name, type_format)
        for name in DATASETS
    }
    maps = load_mappings(mapping_dir)
    mapping_comuni, mapping_vodafone, mapping_apt = (
        maps["mapping_comuni"],
        maps["mapping_vodafone"],
        maps["mapping_apt"],
    )

    # Uniform disaggregation: vodafone presences are split uniformly over comuni; ISPAT alb and
    # extra-alb presences uniformly over comuni and days.
    # Weighted alternatives (by vodafone distribution / by beds) are available through the
    # `space_weights` / `time_weights` kwargs of process_vodafone / process_presenze_ISPAT, see
    # utils/disaggregation.py.
    dict_processed = {
        "popolazione_pr": process_popolazione(std["popolazione"], mapping_comuni),
        "strutture_pr": process_strutture(std["strutture"], mapping_comuni),
        "vodafone_pr": process_vodafone(std["vodafone"], mapping_vodafone),
        "presenze_alb_pr": process_presenze_ISPAT(
            std["presenze_alb"], mapping_apt, PRESENZE_ALB_VALUE_COLS
        ),
        "presenze_extralb_pr": process_presenze_ISPAT(
            std["presenze_extralb"],
            mapping_comuni,
            PRESENZE_XALB_VALUE_COLS,
            provincia=True,
        ),
    }

    save_computed_dfs(
        dict_processed, local=True, type_format=type_format, path_saving=out_dir
    )
    logger.info("Processed data saved in %s", out_dir)
    return dict_processed


if __name__ == "__main__":
    setup_logging()
    process_data()
