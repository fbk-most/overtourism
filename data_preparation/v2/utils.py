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

PROJECT = os.environ.get("PROJECT_NAME", "overtourism")
BUCKET_NAME = os.environ.get("S3_BUCKET", "datalake")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://minio:9000")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "overtourism/inputdata/")
BASE_DIR = os.environ.get("BASE_DIR", os.getcwd())
CLI_ENV = os.environ.get("CLI_ENV", "aixpa")
PATH_SAVE = Path(__file__).resolve().parent / "processed_data_trentino"

def get_dataframe(name: str) -> DataFrame:
    return dh.get_dataitem(name, project=PROJECT).as_df()

def get_json_s3(name: str) -> dict:
    """Scarica e parsa un JSON da S3, es. get_json_s3('mapping_ids/mapping_comuni_ISTAT.json')."""
    buffer = get_s3(name)
    return json.load(buffer)

def put_dataframe(df: pd.DataFrame, name: str, type: str = "parquet", path: Path = PATH_SAVE) -> str:
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

def init_s3_dhcli(env = "most-platform"):
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

    s3 = boto3.resource('s3',
                        endpoint_url=aws_endpoint_url,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        aws_session_token=aws_session_token)


    bucket = s3.Bucket('most-datalake')
    return s3, bucket

s3, bucket = None, None

def init_s3(force = False):
    global s3, bucket
    if s3 is None or bucket is None or force:
        s3, bucket = init_s3_dhcli("most-platform")
    return s3, bucket

def get_s3(name: str):
    s3, bucket = init_s3()
    object = s3.Object('most-datalake', 'overtourism/inputdata/' + name)

    buffer = io.BytesIO()
    object.download_fileobj(buffer)
    buffer.seek(0)
    return buffer



def read_shapefile_s3(base_path: str) -> gpd.GeoDataFrame:
    """
    Downloads shapefile files (.shp, .shx, .dbf, .prj) and returns a pandas GeoDataFrame.
    """
    _, bucket = init_s3()
    
    if base_path.endswith('.shp'):
        base_path = base_path[:-4]
        
    s3_prefix = 'overtourism/inputdata/' + base_path
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        downloaded_shp = None

        for obj in bucket.objects.filter(Prefix=s3_prefix):
            file_name = Path(obj.key).name
            local_file_path = temp_path / file_name
            
            bucket.download_file(obj.key, str(local_file_path))
            
            if file_name.endswith('.shp'):
                downloaded_shp = local_file_path

        if downloaded_shp is None:
            raise FileNotFoundError(f"Nessun file .shp trovato per il prefisso: {s3_prefix}")

        gdf = gpd.read_file(downloaded_shp)
    return gdf


if __name__== "__main__":
    df = get_dataframe("popolazione_2020_2024")
    gjs = get_s3("TRENTINO-comuni_Vodafone_2023.geojson")
    print(df.head())
    