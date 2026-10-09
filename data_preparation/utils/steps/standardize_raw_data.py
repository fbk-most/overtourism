# SPDX-License-Identifier: Apache-2.0
"""
STEP 1 - Standardization.

Input : Output/data/raw_data/
Output: Output/data/normalized/   (popolazione_std, strutture_std, vodafone_std)

The ISPAT presences (alb / extralb arrivals and presences) are NOT normalized: they are processed from raw_data.

Uniformation of the raw data (names, DATA/LOCATION, dates and comune format).
No filtering and no aggregation.
"""

import logging
from pathlib import Path

import pandas as pd

from utils.cleaning import (
    customize_unidecode,
    standard_ordering_cols,
    to_data_location,
)
from utils.config import (
    NORMALIZED_DIR,
    RAW_DIR,
    MAPPING_DIR,
    REFERENCES,
    TYPE_FORMAT,
    setup_logging,
)
from utils.io import read_df, save_computed_dfs

logger = logging.getLogger(__name__)


def convert_vodafone_comuni(df, geojson_comuni_json_data):
    """Conversion from locId (geojson) to comune name"""
    location_map = (
        geojson_comuni_json_data.set_index("id")["name"].str.upper().to_dict()
    )
    return df["locId"].map(location_map)


def _standardize_columns(df, date_col="anno", df_name=None):
    """Basic standardization: comune/data schema -> DATA/LOCATION."""
    logger.info(
        "Applying standardization to data%s", f" '{df_name}'" if df_name else ""
    )
    return to_data_location(df, date_col=date_col)


def _standardize_comune_yearly(df, comune_col, date_col, df_name):
    """Comune names cleaned + DATA/LOCATION schema (popolazione, strutture: municipality, yearly)."""
    df[comune_col] = df[comune_col].apply(customize_unidecode)
    return standard_ordering_cols(
        _standardize_columns(df, date_col=date_col, df_name=df_name)
    )


def standardize_popolazione_columns(
    df, comune_col="comune", date_col="anno"
) -> pd.DataFrame:
    """popolazione: granularity municipality, yearly"""
    return _standardize_comune_yearly(df, comune_col, date_col, "popolazione_df")


def standardize_strutture_columns(
    df, comune_col="comune", date_col="anno"
) -> pd.DataFrame:
    """strutture: granularity municipality, yearly"""
    return _standardize_comune_yearly(df, comune_col, date_col, "strutture_df")


def standardize_vodafone_columns(
    df, geojson_comuni_json_data, comune_col="comune", date_col="date"
):
    """vodafone presences: granularity vodafone areas, daily"""
    df[comune_col] = convert_vodafone_comuni(df, geojson_comuni_json_data)
    logger.info(
        "Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)"
    )
    mask = df[comune_col].isin(["VIGO DI FASSA", "POZZA DI FASSA"])
    df.loc[mask, comune_col] = "SAN GIOVANNI DI FASSA"
    df = _standardize_columns(df, date_col=date_col, df_name="vodafone_df")
    df.rename(columns={"value": "presenze"}, inplace=True)
    return standard_ordering_cols(df)


def standardize_raw_data(
    raw_dir=RAW_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=NORMALIZED_DIR,
    type_format=TYPE_FORMAT,
):
    from utils.readers import read_geojson

    raw_dir = Path(raw_dir)
    mapping_dir = Path(MAPPING_DIR)

    logger.info("Reading raw data from %s", raw_dir)
    popolazione_df = read_df(raw_dir, "popolazione_2020_2024", type_format)
    strutture_df = pd.read_csv(raw_dir / "Annuario-TavXIII-per-comune-csv.csv")
    vodafone_df = read_df(raw_dir, "vodafone_attendences", type_format)
    geojson = read_geojson(mapping_dir / Path(REFERENCES["geojson"]).name)

    dict_std = {
        "popolazione_std": standardize_popolazione_columns(popolazione_df),
        "strutture_std": standardize_strutture_columns(strutture_df),
        "vodafone_std": standardize_vodafone_columns(vodafone_df, geojson),
    }
    save_computed_dfs(
        dict_std, local=True, type_format=type_format, path_saving=out_dir
    )
    logger.info("Standardized data saved in %s", out_dir)
    return dict_std


if __name__ == "__main__":
    setup_logging()
    standardize_raw_data()
