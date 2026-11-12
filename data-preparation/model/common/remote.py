# SPDX-License-Identifier: Apache-2.0
"""Access of the model pipelines to the platform (DigitalHub) and to the S3 data lake.

Heavy / optional dependencies (digitalhub, boto3) are imported lazily, so that the rest of the package
(and the test-suite) works without them. Subset of territorial_indexes/utils/remote.py: only what the models use.
"""

import configparser
import logging
from pathlib import Path

from model.common.config import PROJECT, S3_BUCKET, S3_ENV

logger = logging.getLogger(__name__)

_s3 = None
_bucket = None


def log_dataframe(file_path, name: str, type: str = "parquet"):
    """Uploads an already-saved dataframe file to the platform."""
    import digitalhub as dh

    if type not in {"parquet", "csv"}:
        raise NotImplementedError(f"Unsupported type: {type}.")
    project = dh.get_or_create_project(PROJECT)
    return project.log_table(f"{name}.{type}", source=str(file_path), file_format=type)


def _s3_credentials(env: str) -> dict:
    """Credentials from ~/.dhcore.ini (DHCLI)."""
    config = configparser.ConfigParser()
    config.read(Path.home() / ".dhcore.ini")
    section = config[env]
    return {
        "endpoint_url": section["aws_endpoint_url"],
        "aws_access_key_id": section["aws_access_key_id"],
        "aws_secret_access_key": section["aws_secret_access_key"],
        "aws_session_token": section["aws_session_token"],
    }


def init_s3_dhcli(env=S3_ENV):
    """Returns (s3 resource, bucket)."""
    import boto3

    s3 = boto3.resource("s3", **_s3_credentials(env))
    return s3, s3.Bucket(S3_BUCKET)


def init_s3(force=False):
    global _s3, _bucket
    if _s3 is None or _bucket is None or force:
        _s3, _bucket = init_s3_dhcli()
    return _s3, _bucket
