# SPDX-License-Identifier: Apache-2.0
"""Local write of dataframes for the model pipelines (optionally logged to the platform).
No network / platform dependency at import time."""

import logging
from pathlib import Path

import pandas as pd

from model.common.config import TYPE_FORMATS

logger = logging.getLogger(__name__)


def ensure_dir(path) -> Path:
    """Creates `path` (and parents) if needed and returns it as a Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def put_dataframe(df: pd.DataFrame, name: str, path, type: str = "parquet") -> str:
    """Saves a dataframe as <path>/<name>.<type> and returns the file path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    path = path / name
    match type:
        case "json":
            path = path.with_suffix(".json")
            df.to_json(path, orient="index", indent=4)
        case "csv":
            path = path.with_suffix(".csv")
            df.to_csv(path, index=False)
        case "parquet":
            path = path.with_suffix(".parquet")
            df.to_parquet(path, index=False)
        case _:
            raise NotImplementedError(f"Unsupported type: {type}")
    return str(path)


def save_computed_dfs(dict_dfs, local=False, type_format="parquet", path_saving=None):
    """Writes every dataframe in `path_saving`; with local=False it also logs it to the platform.

    `path_saving` is mandatory: there is deliberately no default location.
    """
    if path_saving is None:
        raise ValueError("path_saving is required")
    if type_format not in TYPE_FORMATS:
        raise ValueError(
            f"type_format must be one of {TYPE_FORMATS}, got {type_format!r}"
        )
    for key, value in dict_dfs.items():
        logger.info(
            "Saving dataframe '%s' in %s/%s.%s...", key, path_saving, key, type_format
        )
        file_path = put_dataframe(value, key, path=path_saving, type=type_format)
        if not local:
            from model.common.remote import log_dataframe

            logger.info(
                "Logging dataframe '%s.%s' to the platform...", key, type_format
            )
            log_dataframe(file_path, key, type=type_format)
    logger.info("## Saved.")
