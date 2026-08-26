# SPDX-License-Identifier: Apache-2.0
from pandas.core.interchange.dataframe_protocol import DataFrame
import digitalhub as dh
import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
import tempfile
import io
import boto3
import configparser
import json
from unidecode import unidecode
import logging

logging.basicConfig(level=logging.INFO)


PROJECT = os.environ.get("PROJECT_NAME", "overtourism")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "overtourism/inputdata/")
BASE_DIR = os.environ.get("BASE_DIR", str(Path.cwd()))

TEMP_FOLDER_DIR = Path(__file__).resolve().parents[1] / "Output"
TEMP_FOLDER_DIR.mkdir(parents=True, exist_ok=True)

PATH_SAVE = TEMP_FOLDER_DIR / "processed_data_trentino"

PATH_OVERTOURISM = Path(__file__).parents[4].resolve()
PATH_AIXPA_INDEX_DFS = (
    PATH_OVERTOURISM
    / "overtourism"
    / "overtourism"
    / "overtourism"
    / "database"
    / "index_data_v2"
)
PATH_AIXPA_INDEX_DFS.mkdir(parents=True, exist_ok=True)


MAPPING_COMUNI_FILE = (
    Path(__file__).resolve().parents[2] / "mapping" / "mapping_comuni_ISTAT.json"
)

# Explicit overrides for comuni whose official Italian name differs from
# a naive "before the dash" split of the bilingual name in the source CSV.
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


## UTILS FUNCTIONS
## Some functions for decoding / padding / cleaning
def get_mapping_comuni():
    with MAPPING_COMUNI_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def customize_unidecode(x):
    """
    Convert the input string, removing accents, converting to uppercase, and stripping whitespace.
    """
    if x.endswith("'"):  # removes also trailing apostrophe if present
        x = x.removesuffix("'")
    return unidecode(x.strip().upper())


def pad_id_comune(series, width=6):
    """Zero-pad an ID_COMUNE column to `width` digits (e.g. 22001 -> '022001').

    Missing / unmapped values (NaN) are left untouched. Works regardless of
    whether the column arrives as int, float (common when NaNs are present),
    or string dtype.
    """

    def _pad(x):
        if pd.isna(x):
            return x
        return str(int(x)).zfill(width)

    return series.apply(_pad)


def _remove_provincia(df, comune_col="comune", upper=False):
    """Drop rows whose comune starts with 'PROVINCIA', logging what gets removed."""
    series = df[comune_col].str.upper() if upper else df[comune_col]
    mask = series.str.startswith("PROVINCIA")
    if mask.any():
        logging.info(
            f"Comune {df.loc[mask, comune_col].unique()} is a PROVINCIA, removing it from the analysis"
        )
        df = df[~mask]
    return df


def _to_data_location(df, date_col, drop_cols=None):
    """Standardize a phenomenon dataframe to DATA/LOCATION column naming.

    date_col: name of the column holding the time dimension (e.g. "anno" or "date").
    drop_cols: optional columns to drop before returning (e.g. a redundant "anno"
    column once the daily "date" column is promoted to DATA).
    """
    df = df.drop(columns=drop_cols) if drop_cols else df
    return df.rename(columns={date_col: "DATA", "comune": "LOCATION"})


def resolve_id_comune(name, mapping_comuni, overrides=COMUNE_NAME_OVERRIDES):
    """Map a comune name to its ISTAT ID, falling back to the bilingual-name overrides."""
    id_comune = mapping_comuni.get(name)
    if id_comune is None and name in overrides:
        id_comune = mapping_comuni.get(overrides[name])
    return id_comune


## S3 utilities


def get_dataframe(name: str) -> DataFrame:
    return dh.get_dataitem(name, project=PROJECT).as_df()


def get_json_s3(name: str) -> dict:
    """Scarica e parsa un JSON da S3, es. get_json_s3('mapping_ids/mapping_comuni_ISTAT.json')."""
    buffer = get_s3(name)
    return json.load(buffer)


def put_dataframe(
    df: pd.DataFrame, name: str, type: str = "parquet", path: Path = PATH_SAVE
) -> str:
    """Saves a dataframe"""
    path.mkdir(parents=True, exist_ok=True)
    path = path / name
    match type:
        case "json":
            path = path.with_suffix(".json")
            df.to_json(path, orient="index", indent=4)
        case "csv":
            path = path.with_suffix(".csv")
            df.to_csv(path)
        case "parquet":
            path = path.with_suffix(".parquet")
            df.to_parquet(path)
        case _:
            raise NotImplementedError(f"Unsupported type: {type}")
    return str(path)


def log_dataframe(df: pd.DataFrame, name: str, type: str = "parquet"):
    """Uploads a dataframe."""
    file_path = put_dataframe(df, name, type=type)
    project = dh.get_or_create_project(PROJECT)

    if type in {"parquet", "csv"}:
        return project.log_table(f"{name}.{type}", source=file_path, file_format=type)

    raise NotImplementedError(f"Unsupported type: {type}.")


def init_s3_dhcli(env="aixpa"):
    """
    Initialize S3 connection for overtourism analysis.
        Parameters:
            env: environment name
        Returns:
            s3: S3 resource object
            bucket: S3 bucket object
    NOTE: Specific to the DHCLI-based access to platform.
    """
    home = Path.home()

    config = configparser.ConfigParser()
    config.read(home / ".dhcore.ini")
    aws_endpoint_url = config[env]["aws_endpoint_url"]
    aws_access_key_id = config[env]["aws_access_key_id"]
    aws_secret_access_key = config[env]["aws_secret_access_key"]
    aws_session_token = config[env]["aws_session_token"]

    s3 = boto3.resource(
        "s3",
        endpoint_url=aws_endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )

    bucket = s3.Bucket("most-datalake")
    return s3, bucket


s3, bucket = None, None


def init_s3(force=False):
    global s3, bucket
    if s3 is None or bucket is None or force:
        s3, bucket = init_s3_dhcli("aixpa")
    return s3, bucket


def get_s3(name: str):
    s3, bucket = init_s3()
    object = s3.Object("most-datalake", "overtourism/inputdata/" + name)

    buffer = io.BytesIO()
    object.download_fileobj(buffer)
    buffer.seek(0)
    return buffer


def read_shapefile_s3(base_path: str) -> gpd.GeoDataFrame:
    """
    Downloads shapefile files (.shp, .shx, .dbf, .prj) and returns a pandas GeoDataFrame.
    """
    _, bucket = init_s3()

    if base_path.endswith(".shp"):
        base_path = base_path[:-4]

    s3_prefix = "overtourism/inputdata/" + base_path

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        downloaded_shp = None

        for obj in bucket.objects.filter(Prefix=s3_prefix):
            file_name = Path(obj.key).name
            local_file_path = temp_path / file_name

            bucket.download_file(obj.key, str(local_file_path))

            if file_name.endswith(".shp"):
                downloaded_shp = local_file_path

        if downloaded_shp is None:
            raise FileNotFoundError(
                f"Nessun file .shp trovato per il prefisso: {s3_prefix}"
            )

        gdf = gpd.read_file(downloaded_shp)
    return gdf


def save_computed_dfs(dict_dfs, local=False):
    for key, value in dict_dfs.items():
        logging.info(f"Uploading dataframe '{key}'...")
        put_dataframe(value, key, type="parquet", path=PATH_AIXPA_INDEX_DFS)
        if not local:
            logging.info(f"Logging dataframe '{key}.parquet'...")
            log_dataframe(value, key, type="parquet")
    logging.info("## Saved.")


if __name__ == "__main__":
    df = get_dataframe("popolazione_2020_2024")
    gjs = get_s3("TRENTINO-comuni_Vodafone_2023.geojson")
    print(df.head())
    
