# SPDX-License-Identifier: Apache-2.0
"""
STEP 1 - Standardization.

Input : Output/raw_data/
Output: Output/normalized/   (popolazione_std, strutture_std, vodafone_std,
                              presenze_alb_std, presenze_extralb_std)

Uniformation of the raw data (names, DATA/LOCATION, dates and comune format).
"""

import logging
from pathlib import Path

import geopandas as geopd
import pandas as pd

from data_preparation.utils.utils import save_computed_dfs
from data_preparation.utils.common import (
    RAW_DIR,
    NORMALIZED_DIR,
    read_df,
    customize_unidecode,
    standard_ordering_cols,
    _to_data_location,
)

logging.basicConfig(level=logging.INFO)


## HELPER FUNCTIONS
def convert_vodafone_comuni(df, geojson_comuni_json_data):
    """Conversion from locId (geojson) to comune name"""
    location_map = (
        geojson_comuni_json_data.set_index("id")["name"].str.upper().to_dict()
    )
    return df["locId"].map(location_map)


def _standardize_columns(df, date_col="anno", df_name=None):
    """Basic standardization: comune/data schema -> DATA/LOCATION/ID_COMUNE."""
    logging.info(
        "Applying standardization to data%s", f" '{df_name}'" if df_name else ""
    )
    df = _to_data_location(df, date_col=date_col)
    return df



## 2. STANDARDIZATION: putting the columns in a standard format 
def standardize_popolazione_columns(df,comune_col = "comune", date_col="anno") -> pd.DataFrame:
    """Standardizes popolazione df, granularity: municipality, yearly"""
    df[comune_col] = df[comune_col].apply(customize_unidecode) # riformattiamo i nomi dei comuni 
    return standard_ordering_cols(_standardize_columns(df, date_col=date_col, df_name = "popolazione_df"))

def standardize_strutture_columns(df,comune_col = "comune", date_col = "anno") -> pd.DataFrame:
    """Standardizes strutture df, granularity: municipality, yearly"""
    df[comune_col] = df[comune_col].apply(customize_unidecode)
    return standard_ordering_cols(_standardize_columns(df, date_col=date_col, df_name = "strutture_df"))

def standardize_vodafone_columns(df,geojson_comuni_json_data, comune_col = "comune", date_col="date"):
    """Standardizes strutture df, granularity: vodafone areas, daily"""
    df[comune_col] = convert_vodafone_comuni(df,geojson_comuni_json_data)
    # Unify Vigo di Fassa and Pozza di Fassa
    logging.info(
        "Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)"
    )
    mask = df[comune_col].isin(["VIGO DI FASSA", "POZZA DI FASSA"])
    df.loc[mask, comune_col] = "SAN GIOVANNI DI FASSA"
    df = _standardize_columns(df, date_col = date_col, df_name = "vodafone_df")
    df.rename(columns = {"value": "presenze"}, inplace = True)
    return standard_ordering_cols(df)

def standardize_presenze_columns(df, cols_renaming:dict, date_col="data"):
    """Standardizes presences df, alb, granularity: APT, monthly"""
    df.rename(columns = cols_renaming, inplace=True)
    df[date_col] = pd.to_datetime(
        {
            "year": df["Anno"].astype(int),
            "month": df["Mese"],
            "day": 1,
        }
    )
    df =_standardize_columns(
            df,
            date_col = date_col,
            df_name = "presenze_df"
        )
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return standard_ordering_cols(df)


## Standardization of raw data: main step
def standardize_raw_data(raw_dir=RAW_DIR, out_dir=NORMALIZED_DIR, type_format="csv"):
    raw_dir = Path(raw_dir)

    logging.info("Reading raw data from %s", raw_dir)
    popolazione_df = read_df(raw_dir, "popolazione_2020_2024", type_format)
    strutture_df = pd.read_csv(raw_dir / "Annuario-TavXIII-per-comune-csv.csv")
    vodafone_df = read_df(raw_dir, "vodafone_attendences", type_format)
    presenze_alb_df = pd.read_csv(raw_dir / "presenze_Trentino_ISPAT.csv")
    presenze_extralb_df = pd.read_csv(raw_dir / "presenze_Trentino_ISPAT_alb_xalb.csv")
    geojson = geopd.read_file(raw_dir / "TRENTINO-comuni_Vodafone_2023.geojson")

    dict_std = {
        "popolazione_std": standardize_popolazione_columns(popolazione_df),
        "strutture_std": standardize_strutture_columns(strutture_df),
        "vodafone_std": standardize_vodafone_columns(vodafone_df, geojson),
        "presenze_alb_std": standardize_presenze_columns(
            presenze_alb_df, {"Ambito": "comune", "Presenze": "presenze_alb"}
        ),
        "presenze_extralb_std": standardize_presenze_columns(
            presenze_extralb_df,
            {
                "Presenze alberghi": "presenze_alb",
                "Presenze extra-alberghi": "presenze_xalb",
            },
        ),
    }
    save_computed_dfs(
        dict_std,
        local=True,
        type_format=type_format,
        path_saving=out_dir,
    )
    logging.info("Standardized data saved in %s", out_dir)
    return dict_std


if __name__ == "__main__":
    dir_in = RAW_DIR
    dir_out = NORMALIZED_DIR
    type_format = "csv"
    standardize_raw_data(dir_in, dir_out, type_format)
