# SPDX-License-Identifier: Apache-2.0
"""Merge of the newly processed data into the existing processed data."""

import logging

import pandas as pd

from data_preparation.utils.cleaning import make_hashable, standard_ordering_cols
from data_preparation.utils.datasets import DATASETS

logger = logging.getLogger(__name__)


def merge_new_pr_dataframe(df_old, df_new, value_cols, dataset_name="dataset"):
    """Merges old and new on DATA + ID_COMUNE (ID_COMUNE may be lists, hence make_hashable).
    On overlap the NEW rows win. Only DATA, ID_COMUNE and value_cols are kept."""
    required = {"DATA", "ID_COMUNE", *value_cols}
    if not required.issubset(df_old.columns):
        raise ValueError(
            f"[{dataset_name}] columns {sorted(required - set(df_old.columns))} missing in OLD data"
        )
    if not required.issubset(df_new.columns):
        raise ValueError(
            f"[{dataset_name}] columns {sorted(required - set(df_new.columns))} missing in NEW data"
        )

    old_keys = set(zip(df_old["DATA"], df_old["ID_COMUNE"].map(make_hashable)))
    new_keys = set(zip(df_new["DATA"], df_new["ID_COMUNE"].map(make_hashable)))
    replaced_keys = old_keys & new_keys
    replaced_dates = {k[0] for k in replaced_keys if pd.notna(k[0])}
    range_str = (
        f"from {min(replaced_dates)} to {max(replaced_dates)}"
        if replaced_dates
        else "no interval"
    )

    logger.info(
        "Merge stats [%s - %s]: %d new rows -> %d records replaced on %d dates (%s).",
        dataset_name,
        ", ".join(value_cols),
        len(df_new),
        len(replaced_keys),
        len(replaced_dates),
        range_str,
    )

    cols = ["DATA", "ID_COMUNE", *value_cols]
    merged = pd.concat([df_old[cols], df_new[cols]], ignore_index=True).copy()
    merged["_ID_KEY"] = merged["ID_COMUNE"].map(
        make_hashable
    )  # tuples: avoids list-type problems
    merged = (
        merged.drop_duplicates(subset=["DATA", "_ID_KEY"], keep="last")
        .sort_values(["DATA", "_ID_KEY"])
        .drop(columns="_ID_KEY")
        .reset_index(drop=True)
    )
    return standard_ordering_cols(merged)


def merge_all_processed_dataframes(old_dfs: dict, new_dfs: dict) -> dict:
    """Merge existing processed data with the update. Returns only what the update touched:
    the merged `<dataset>_pr` frames."""
    merged = {}
    update_names = {spec.update_name: spec for spec in DATASETS.values()}
    for name, df in new_dfs.items():
        spec = update_names.get(name)
        if spec is None:
            raise ValueError(
                f"Update frame {name!r} does not correspond to a registered dataset"
            )
        merged[spec.processed_name] = merge_new_pr_dataframe(
            old_dfs[spec.processed_name],
            df,
            list(spec.value_cols),
            dataset_name=spec.name,
        )
    return merged
