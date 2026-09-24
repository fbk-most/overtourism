import logging
import pandas as pd
from pathlib import Path 
import geopandas as geopd
from data_preparation.v2.utils.utils import (
    get_dataframe,
    get_s3,    
    get_mapping,
    save_computed_dfs,
    pad_id_comune,
    customize_unidecode,
    resolve_id_comune,
    standard_ordering_cols,
   _remove_provincia,
    _to_data_location,
)

SAVEPATH_STD_DATA = Path(__file__).parent / "data_std"

## CONSTANT VARIABLES 
## just the minimal cols 

STRUTTURE_VALUE_COLS = [
    "tot_postiletto_non_conv",
    "tot_postiletto",
    "tot_strutture_non_conv",
    "tot_strutture",
]
VODAFONE_VALUE_COLS = [
    'presenze'
]
POPOLAZIONE_VALUE_COLS = [
    "popolazione"
]
PRESENZE_ALB_VALUE_COLS = [
    "presenze_alb"
]
PRESENZE_XALB_VALUE_COLS = [
    'presenze_xalb'  # presenze_alb
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

RENAMING_STRUTTURE = {
    "alberghieri posti_letto": "tot_postiletto_alberghieri",
    "extra alb. Posti_letto": "tot_postiletto_extralberghieri",
    
    "alberghieri strutture" : "tot_strutture_alberghiere",
    "extra alb. Strutture" : "tot_strutture_extralberghiere",

    "all. privati numero": "tot_strutture_non_conv",
    "all. privati posti_letto": "tot_postiletto_non_conv",

    "tot convenzionali posti_letto": "tot_postiletto_conv",
    "tot convenzionali strutture": "tot_strutture_conv"
}

## 0. HELPER FUNCTIONS
def convert_vodafone_comuni(df, geojson_comuni_json_data):
    """Helper function for conversion from locId geojson to comune"""
    location_map = geojson_comuni_json_data.set_index("id")["name"].str.upper().to_dict()
    return df["locId"].map(
        location_map
    )

## 1. LOADING RAW DATA 
def load_raw_data():
    """Leading raw data to a standardized format"""
    ## updload mapping and geojson data 
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    mapping_apt = get_mapping("map_comuni_into_apt.json")
    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))

    ## Uploading dataframes 
    logging.info("Downloading dataframe 'popolazione_2020_2024'...")
    popolazione_df = get_dataframe("popolazione_2020_2024")
    logging.info("Downloading Annuario-TavXIII-per-comune-csv.csv from S3...")
    strutture_df = pd.read_csv(get_s3("Annuario-TavXIII-per-comune-csv.csv"))
    logging.info("Downloading dataframe 'vodafone_attendences'...")
    vodafone_df = get_dataframe("vodafone_attendences")
    logging.info("Downloading presenze_Trentino_ISPAT.csv from S3...")
    presenze_ispat = pd.read_csv(get_s3("presenze_Trentino_ISPAT.csv"))
    logging.info("Downloading presenze_Trentino_ISPAT_alb_xalb.csv from S3...")
    presenze_df_extralb = pd.read_csv(get_s3("presenze_Trentino_ISPAT_alb_xalb.csv"))
    logging.info("Downloading mapping_ids/map_comuni_into_apt.json from S3...")

    return {
            "mapping_comuni" : mapping_comuni, 
            "mapping_vodafone": mapping_vodafone, 
            "mapping_apt": mapping_apt,
            "geojson_comuni_json_data": geojson_comuni_json_data,
            "popolazione_df": popolazione_df,
            "strutture_df": strutture_df, 
            "vodafone_df": vodafone_df, 
            "presenze_df_alb": presenze_ispat,
            "presenze_df_extralb": presenze_df_extralb
        }


## STANDARDIZATION:
## The following functions are used to standardize all the datasets in a common format  

## Filtering helper functions: used for filtering the dataframes of interest

def _filtering_strutture(df, min_year, year_col="DATA"):
    """Excludes years pre-2020, geography changes for munidcipalities aggregations"""
    return df[df[year_col] > min_year].copy()

def _filtering_vodafone_attendences(df):
    "Filtering presences on tourists and municipalities"
    return df[
        (df["userProfile"] == "TOURIST")
        & (df["locType"] == "TN_MKT_AL_3")
    ].copy()

# Standardization function

def _standardize_columns(df, date_col = "anno", df_name = None):
    """Basic standardization: comune/data schema -> DATA/LOCATION/ID_COMUNE."""
    logging.info(
        "Applying standardization to data%s",
        f" '{df_name}'" if df_name else ""
    )   
    df = _to_data_location(df, date_col=date_col)
    return df 


## 2. STANDARDIZATION: putting the columns in a standard format 
def standardize_popolazione_columns(df) -> pd.DataFrame:
    """Standardizes popolazione df, granularity: municipality, yearly"""
    df["comune"] = df["comune"].apply(customize_unidecode) # riformattiamo i nomi dei comuni 
    return standard_ordering_cols(_standardize_columns(df, date_col="anno", df_name = "popolazione_df"))

def standardize_strutture_columns(df) -> pd.DataFrame:
    """Standardizes strutture df, granularity: municipality, yearly"""
    df["comune"] = df["comune"].apply(customize_unidecode)
    return standard_ordering_cols(_standardize_columns(df, date_col="anno", df_name = "strutture_df"))

def standardize_vodafone_columns(df,geojson_comuni_json_data):
    """Standardizes strutture df, granularity: vodafone areas, daily"""
    df["comune"] = convert_vodafone_comuni(df,geojson_comuni_json_data)
    # Unify Vigo di Fassa and Pozza di Fassa
    logging.info(
        "Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)"
    )
    mask = df["comune"].isin(["VIGO DI FASSA", "POZZA DI FASSA"])
    df.loc[mask, "comune"] = "SAN GIOVANNI DI FASSA"

    df = _standardize_columns(df, date_col = "date", df_name = "vodafone_df")
    df.rename(columns = {"value": "presenze"}, inplace = True)
    return standard_ordering_cols(df)

def stadardize_presenze_columns(df, cols_renaming:dict):
    """Standardizes presences df, alb, granularity: APT, monthly"""
    df.rename(columns = cols_renaming, inplace=True)
    df["data"] = pd.to_datetime(
        {
            "year": df["Anno"].astype(int),
            "month": df["Mese"],
            "day": 1,
        }
    )
    df =_standardize_columns(
            df,
            date_col = 'data',
            df_name = "presenze_df"
        )
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return standard_ordering_cols(df)

def standardize_columns(dict_raw_data):
    # 2. Standardize data
    popolazione_df = standardize_popolazione_columns(dict_raw_data['popolazione_df'])
    strutture_df = standardize_strutture_columns(dict_raw_data['strutture_df'])
    vodafone_df = standardize_vodafone_columns(dict_raw_data['vodafone_df'], geojson_comuni_json_data=dict_raw_data['geojson_comuni_json_data'])
    presenze_df_alb = stadardize_presenze_columns(dict_raw_data['presenze_df_alb'],cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"}) 
    presenze_df_extralb = stadardize_presenze_columns(dict_raw_data['presenze_df_extralb'], cols_renaming={"Presenze alberghi": "presenze_alb","Presenze extra-alberghi": "presenze_xalb",})

    return {
        "popolazione_std" : popolazione_df,
        "strutture_std" : strutture_df,
        "vodafone_std" : vodafone_df,
        "presenze_alb_std" : presenze_df_alb,
        "presenze_extralb_std": presenze_df_extralb,
        "mapping_comuni": dict_raw_data['mapping_comuni'],
        "mapping_vodafone": dict_raw_data['mapping_vodafone'],
        "mapping_apt": dict_raw_data['mapping_apt']
        }

## 3. PROCESS DATA: Take the desired columns, filtering ...

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
    df["tot_strutture"] = (
        df["tot_strutture_conv"]
        + df["tot_strutture_non_conv"]
    )
    df["tot_postiletto"] = (
        df["tot_postiletto_conv"]
        + df["tot_postiletto_non_conv"]
    )
    # Set ID_COMUNE (resolving the bilingual overrides)
    df["ID_COMUNE"] = df["LOCATION"].apply(lambda x: resolve_id_comune(x, mapping_comuni))

    if df["ID_COMUNE"].isna().any():
        if len(df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique()) > 0:
            logging.warning(
                f"[process_strutture] Nessun ID_COMUNE trovato (anche con overrides) per: {sorted(df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique())}"
            )

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])   # apply padding on these IDs
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + STRUTTURE_VALUE_COLS])

def process_vodafone(df, mapping_vodafone):
    """Standardizes presences df, registered by vodafone, granularity: vodafone aggregations, daily"""
    ## Filtering the attendences on COMUNI & TURISTI 
    df = _filtering_vodafone_attendences(df)
    df["ID_COMUNE"] = df["LOCATION"].map(
        mapping_vodafone
    )
    mask = (df["LOCATION"] == 'SAN GIOVANNI DI FASSA')
    df.loc[mask, "ID_COMUNE"] = pd.Series([[22250]] * mask.sum(), index=df.index[mask], dtype=object)
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + VODAFONE_VALUE_COLS]) 


def process_presenze_ISPAT(df, mapping_comuni, value_cols, provincia = False):
    """Standardizes presences df, alb, granularity: APT, monthly"""
    df.drop(columns=["Anno", "Mese"], inplace=True)
    df.sort_values(by = "DATA")
    if provincia: 
        df["LOCATION"] = "PROVINCIA"
        df["ID_COMUNE"] = [list(mapping_comuni.values())] * len(df)
    else:
        df["ID_COMUNE"] = df["LOCATION"].map(mapping_comuni).apply(
            lambda x: [int(i) for i in x] if isinstance(x, list) else x
        )
        df = _remove_provincia(df,"LOCATION", True)
    df['ID_COMUNE'] = pad_id_comune(df["ID_COMUNE"])    
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + value_cols])


def process_data(dict_std_data):
    # 3. Process data
    popolazione_df = process_popolazione(dict_std_data['popolazione_std'], dict_std_data['mapping_comuni'])
    strutture_df = process_strutture(dict_std_data['strutture_std'], dict_std_data['mapping_comuni'])
    vodafone_df = process_vodafone(dict_std_data['vodafone_std'], dict_std_data['mapping_vodafone'])
    presenze_df_alb = process_presenze_ISPAT(dict_std_data['presenze_alb_std'],dict_std_data['mapping_apt'], PRESENZE_ALB_VALUE_COLS) 
    presenze_df_extralb = process_presenze_ISPAT(dict_std_data['presenze_extralb_std'], dict_std_data['mapping_comuni'], PRESENZE_XALB_VALUE_COLS, provincia = True)
    logging.info("Processing finished...")
    return {
        "popolazione_pr" : popolazione_df,
        "strutture_pr" : strutture_df,
        "vodafone_pr" : vodafone_df,
        "presenze_alb_pr" : presenze_df_alb,
        "presenze_df_extralb": presenze_df_extralb,
        }


def main(local = True, type_format = "csv"):
    # 1. Loading raw data 
    dict_raw_data = load_raw_data()
    dict_std_data = standardize_columns(dict_raw_data)
    dict_processed_data = process_data(dict_std_data)

    save_path = Path(SAVEPATH_STD_DATA).resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    save_computed_dfs(dict_dfs=dict_processed_data, local = local, type_format = type_format, path_saving=save_path)
    return dict_processed_data


## Standardization function for mapping: 
## to check if necessary 
def standardize_mapping(mapping: dict) -> dict:
    """Standardizes mapping dictionaries:
    - IDs padded strings via pad_id_comune().
    - Names in uppercase without spaces.
    Manages both formats {Nome: ID} and {Nome: [ID1, ID2]}
    """
    if not mapping:
        return {}

    s = pd.Series(mapping)
    s.index = s.index.astype(str).str.upper().str.strip()
    return pad_id_comune(s).to_dict()


if __name__=="__main__":
    main(local=True, type_format="parquet")