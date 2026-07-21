# SPDX-License-Identifier: Apache-2.0
from pandas.core.interchange.dataframe_protocol import DataFrame
import digitalhub as dh
import os
from pathlib import Path
import pandas as pd 
import io
import boto3
import configparser

PROJECT = os.environ.get("PROJECT_NAME", "overtourism")
BUCKET_NAME = os.environ.get("S3_BUCKET", "datalake")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://minio:9000")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "overtourism/inputdata/")
BASE_DIR = os.environ.get("BASE_DIR", os.getcwd())
CLI_ENV = os.environ.get("CLI_ENV", "aixpa")
PATH_SAVE = Path(__file__).resolve().parent / "processed_data_trentino"

def get_dataframe(name: str) -> DataFrame:
    return dh.get_dataitem(name, project=PROJECT).as_df()

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

def log_dataframe(df: pd.DataFrame, name: str):
    """Uploads a dataframe"""
    put_dataframe(df, name, type="parquet")
    project = dh.get_or_create_project(PROJECT)
    project.log_dataitem(name, "table", data=df)


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


if __name__== "__main__":
    df = get_dataframe("popolazione_2020_2024")
    gjs = get_s3("TRENTINO-comuni_Vodafone_2023.geojson")
    print(df.head())
    