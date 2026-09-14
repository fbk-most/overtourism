import logging

import pandas as pd
import geopandas as geopd
from data_preparation.v2.utils.utils import (
    get_dataframe,
    get_s3,
   _remove_provincia,
    _to_data_location,
    pad_id_comune,
    customize_unidecode,
    resolve_id_comune,
    get_mapping
)


STRUTTURE_VALUE_COLS = [
    "tot_postiletto",
    "tot_postiletto_non_conv",
    "tot_postiletto_conv",
    "tot_strutture",
    "tot_strutture_non_conv",
    "tot_postiletto_alberghieri",
    "tot_postiletto_extralberghieri"
]

COMUNE_NAME_OVERRIDES = {
    "CAMPITELLO DI FASSA-CIAMPEDEL": "CAMPITELLO DI FASSA",
    "CAMPODENNO": "CAMPODENNO",  # no dash present, check exact spelling/accents in mapping
    "CANAL SAN BOVO": "CANAL SAN BOVO",
    "CANAZEI-CIANACEI": "CANAZEI",
    "FIEROZZO-VLAROTZ": "FIEROZZO",
    "FRASSILONGO-GARAIT": "FRASSILONGO",
    "LUSERNA-LUSERN": "LUSERNA",
    "MAZZIN-MAZIN": "MAZZIN",
    "MOENA-MOENA": "MOENA",
    "PALU DEL FERSINA-PALAI EN BERSNTOL": "PALU DEL FERSINA",
    "SAN GIOVANNI DI FASSA-SEN JAN": "SAN GIOVANNI DI FASSA",
    "SORAGA DI FASSA-SORAGA": "SORAGA DI FASSA",
}

CATEGORIA_ALBERGHIERI_LETTI = "alberghieri posti_letto"
CATEGORIA_EXTRALBERGHIERI_LETTI = "extra alb. Posti_letto"

#aggiunte
CATEGORIA_ALBERGHIERI_STRUTTURE = "alberghieri strutture"
CATEGORIA_EXTRALBERGHIERI_STRUTTURE = "extra alb. Strutture"

CATEGORIA_ALLOGGI_PRIVATI = "all. privati numero"
CATEGORIA_ALLOGGI_PRIVATI_LETTI = "all. privati posti_letto"

CATEGORIA_TOT_CONVENZIONALI_LETTI = "tot convenzionali posti_letto"
CATEGORIA_TOT_CONVENZIONALI = "tot convenzionali strutture"

## STANDARDIZATION:
## The following functions are used to standardize all the datasets in a common format  

## Filtering helper functions: used for filtering the dataframes of interest
def _filtering_strutture(df, min_year, year_col="anno"):
    """Esclude anni pre-2020, dove la geografia comunale ISTAT cambia per aggregazioni/fusioni di comuni"""
    return df[df[year_col] > min_year].copy()

def _filtering_vodafone_attendences(df):
    # Keep only tourist presences at municipality level
    return df[
        (df["userProfile"] == "TOURIST")
        & (df["locType"] == "TN_MKT_AL_3")
    ].copy()

# Standardization functions 
def _standardize(df, date_col= "anno", remove_provincia=True) -> pd.DataFrame:
    """Basic standardization: comune/data schema -> DATA/LOCATION/ID_COMUNE."""
    logging.info("Applying standardization to data")
    if remove_provincia:
        df = _remove_provincia(df)
    df = _to_data_location(df, date_col=date_col)
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"]) 
    return df

## Spectific functions 
def standardize_popolazione(df, mapping_comuni) -> pd.DataFrame:
    df["comune"] = df["comune"].apply(customize_unidecode)
    df["ID_COMUNE"] = df["comune"].apply(lambda x: resolve_id_comune(x, mapping_comuni))
    return _standardize(df, date_col="anno")


def standardize_strutture(df, mapping_comuni, logging_errors = True):
    df["comune"] = df["comune"].apply(customize_unidecode)
    df["ID_COMUNE"] = df["comune"].apply(lambda x: resolve_id_comune(x, mapping_comuni))
    df = _standardize(df, date_col="anno")

    df = df.rename(columns={
        CATEGORIA_ALBERGHIERI_LETTI: "tot_postiletto_alberghieri",
        CATEGORIA_EXTRALBERGHIERI_LETTI: "tot_postiletto_extralberghieri",
        
        # added
        CATEGORIA_ALBERGHIERI_STRUTTURE : "tot_strutture_alberghiere",
        CATEGORIA_EXTRALBERGHIERI_STRUTTURE : "tot_strutture_extralberghiere",

        CATEGORIA_ALLOGGI_PRIVATI: "tot_strutture_non_conv",
        CATEGORIA_ALLOGGI_PRIVATI_LETTI: "tot_postiletto_non_conv",

        CATEGORIA_TOT_CONVENZIONALI_LETTI: "tot_postiletto_conv",
        CATEGORIA_TOT_CONVENZIONALI: "tot_strutture_conv"
    })

    df["tot_strutture"] = (
        df["tot_strutture_conv"]
        + df["tot_strutture_non_conv"]
    )

    df["tot_postiletto"] = (
        df["tot_postiletto_conv"]
        + df["tot_postiletto_non_conv"]
    )
    unmatched_mask = df["ID_COMUNE"].isna()
    if unmatched_mask.any():
        fallback_names = df.loc[
            unmatched_mask, "LOCATION"
        ].map(COMUNE_NAME_OVERRIDES)
        df.loc[unmatched_mask, "ID_COMUNE"] = (
            fallback_names.map(mapping_comuni)
        )

    if logging_errors:
        num_errate = (df["tot_postiletto_conv"] !=(
                df["tot_postiletto_alberghieri"] + df["tot_postiletto_extralberghieri"]
            )).sum()

        if num_errate > 0 : 
            logging.warning(f"Number of lines such that tot letti convenzionali != sum(letti alberghieri, letti extralberghieri): {num_errate} su {len(df)}")
            logging.warning("Considering sum as the correct value")

        err_strutture = (df["tot_strutture_conv"] != (df["tot_strutture_alberghiere"] + df["tot_strutture_extralberghiere"])).sum()
        if err_strutture > 0:
            logging.warning(f"Mismatch strutture convenzionali in {err_strutture}/{len(df)} lines")
    
        still_missing = df[df["ID_COMUNE"].isna()]["LOCATION"].unique()
        if len(still_missing) > 0:
            print(
                f"[compute_strutture] WARNING: could not find ID_COMUNE for "
                f"{len(still_missing)} comune(s): {sorted(still_missing)}"
            )             
    return df[["DATA", "LOCATION", "ID_COMUNE"] + STRUTTURE_VALUE_COLS]


def standardize_vodafone(df, mapping_vodafone, geojson_comuni_json_data):
    location_map = geojson_comuni_json_data.set_index("id")["name"].str.upper().to_dict()
    df["comune"] = df["locId"].map(
        location_map
    )
    df["ID_COMUNE"] = df["comune"].map(
        mapping_vodafone
    )
    # Unify Vigo di Fassa and Pozza di Fassa
    logging.info(
        "Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)"
    )

    mask = df["comune"].isin(["VIGO DI FASSA", "POZZA DI FASSA"])
    df.loc[mask, "comune"] = "SAN GIOVANNI DI FASSA"
    df.loc[mask, "ID_COMUNE"] = [[22250]] * mask.sum()

    df = _standardize(df, date_col = "date")
    return df


def standardize_raw_data():
    ## updload mapping
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    ## uploading geojson data 
    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))

    ## uploading dataframes 
    logging.info("Downloading dataframe 'popolazione_2020_2024'...")
    popolazione_df = get_dataframe("popolazione_2020_2024")
    logging.info("Downloading Annuario-TavXIII-per-comune-csv.csv from S3...")
    strutture_df = pd.read_csv(get_s3("Annuario-TavXIII-per-comune-csv.csv")) # get_dataframe("Annuario-TavXIII-per-comune-csv")
    logging.info("Downloading dataframe 'vodafone_attendences'...")
    vodafone_df = get_dataframe("vodafone_attendences")

    ## Filtering step (to select data of interest)
    strutture_df = _filtering_strutture(strutture_df, min_year = 2019)
    vodafone_df = _filtering_vodafone_attendences(vodafone_df)

    # Standardize data
    popolazione_df = standardize_popolazione(popolazione_df, mapping_comuni)
    strutture_df = standardize_strutture(strutture_df, mapping_comuni)
    vodafone_df = standardize_vodafone(vodafone_df, mapping_vodafone, geojson_comuni_json_data)

    return popolazione_df, strutture_df, vodafone_df


if __name__=="__main__":
    standardize_raw_data()