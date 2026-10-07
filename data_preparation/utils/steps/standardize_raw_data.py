# SPDX-License-Identifier: Apache-2.0
"""
STEP 1 - Standardization.

Input : Output/data/raw_data/
Output: Output/data/normalized/   (popolazione_std, strutture_std, vodafone_std,
                                   presenze_alb_std, presenze_extralb_std)

Uniformation of the raw data (names, DATA/LOCATION, dates and comune format).
No filtering and no aggregation.
"""

import logging
from pathlib import Path

import pandas as pd

from data_preparation.utils.cleaning import (
    customize_unidecode,
    standard_ordering_cols,
    to_data_location,
)
from data_preparation.utils.config import (
    NORMALIZED_DIR,
    RAW_DIR,
    MAPPING_DIR,
    REFERENCES,
    TYPE_FORMAT,
    setup_logging,
)
from data_preparation.utils.io import read_df, save_computed_dfs

logger = logging.getLogger(__name__)

# column renaming of the two ISPAT presences layouts (shared by base pipeline and update)
PRESENZE_APT_RENAMING = {"Ambito": "comune", "Presenze": "presenze_alb"}
PRESENZE_PROV_RENAMING = {
    "Presenze alberghi": "presenze_alb",
    "Presenze extra-alberghi": "presenze_xalb",
}


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


def standardize_presenze_columns(df, cols_renaming: dict, date_col="data"):
    """ISPAT presences (alb / xalb): granularity APT or provincia, monthly"""
    df.rename(columns=cols_renaming, inplace=True)
    df[date_col] = pd.to_datetime(
        {"year": df["Anno"].astype(int), "month": df["Mese"], "day": 1}
    )
    df = _standardize_columns(df, date_col=date_col, df_name="presenze_df")
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return standard_ordering_cols(df)


def standardize_raw_data(
    raw_dir=RAW_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=NORMALIZED_DIR,
    type_format=TYPE_FORMAT,
):
    from data_preparation.utils.readers import read_geojson

    raw_dir = Path(raw_dir)
    mapping_dir = Path(MAPPING_DIR)

    logger.info("Reading raw data from %s", raw_dir)
    popolazione_df = read_df(raw_dir, "popolazione_2020_2024", type_format)
    strutture_df = pd.read_csv(raw_dir / "Annuario-TavXIII-per-comune-csv.csv")
    vodafone_df = read_df(raw_dir, "vodafone_attendences", type_format)
    presenze_alb_df = pd.read_csv(raw_dir / "presenze_Trentino_ISPAT.csv")
    presenze_extralb_df = pd.read_csv(raw_dir / "presenze_Trentino_ISPAT_alb_xalb.csv")
    geojson = read_geojson(mapping_dir / Path(REFERENCES["geojson"]).name)

    dict_std = {
        "popolazione_std": standardize_popolazione_columns(popolazione_df),
        "strutture_std": standardize_strutture_columns(strutture_df),
        "vodafone_std": standardize_vodafone_columns(vodafone_df, geojson),
        "presenze_alb_std": standardize_presenze_columns(
            presenze_alb_df, PRESENZE_APT_RENAMING
        ),
        "presenze_extralb_std": standardize_presenze_columns(
            presenze_extralb_df, PRESENZE_PROV_RENAMING
        ),
    }
    save_computed_dfs(
        dict_std, local=True, type_format=type_format, path_saving=out_dir
    )
    logger.info("Standardized data saved in %s", out_dir)
    return dict_std


if __name__ == "__main__":
    setup_logging()
    standardize_raw_data()
