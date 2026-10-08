# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 (update) - Processing of the update standardized data.

Input : Output/data/normalized/     (<part>_std, written by standardize_update_raw_data)
        Output/mapping/             (mapping json files, downloaded by the download step)
Output: Output/data/data_processed/ (<dataset>_update_pr)

The processing functions are THE SAME of the base build (process_std_data.py), so every
`<dataset>_update_pr` has exactly the format of the matching base `<dataset>_pr`:
DATA, ID_COMUNE (zero-padded, one comune per row) + the value columns of the dataset, comune x day for
the presences. Parts of the same dataset (e.g. one per year, see `label`) are stacked; later sources
win on a duplicated DATA + ID_COMUNE.
"""

import logging
from pathlib import Path

from data_preparation.utils.adapters import KIND_DATASETS
from data_preparation.utils.cleaning import concat_keep_last
from data_preparation.utils.config import (
    MAPPING_DIR,
    NORMALIZED_DIR,
    PROCESSED_DIR,
    TYPE_FORMAT,
    setup_logging,
)
from data_preparation.utils.datasets import (
    DATASETS,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_XALB_VALUE_COLS,
)
from data_preparation.utils.io import ensure_dir, read_df, save_computed_dfs
from data_preparation.utils.steps.process_std_data import (
    load_mappings,
    process_popolazione,
    process_presenze_ISPAT,
    process_strutture,
    process_vodafone,
)
from data_preparation.utils.update.spec import config_from_argv, load_config, plan_parts

logger = logging.getLogger(__name__)


def _pr_presenze_apt(df, dataset, maps):
    """APT-level presences. Works for alberghiere and extra-alberghiere (value column from the dataset)."""
    processed = process_presenze_ISPAT(
        df, maps["mapping_apt"], PRESENZE_ALB_VALUE_COLS, provincia=False
    )
    out_col = DATASETS[dataset].value_cols[0]
    return processed.rename(columns={"presenze_alb": out_col})


# kind -> processing (same functions of the base build)
PROCESSORS = {
    "popolazione": lambda df, dataset, maps: process_popolazione(df, maps["mapping_comuni"]),
    "strutture": lambda df, dataset, maps: process_strutture(df, maps["mapping_comuni"]),
    "vodafone": lambda df, dataset, maps: process_vodafone(df, maps["mapping_vodafone"]),
    "presenze_apt": _pr_presenze_apt,
    "presenze_prov": lambda df, dataset, maps: process_presenze_ISPAT(
        df,
        maps["mapping_comuni"],
        PRESENZE_XALB_VALUE_COLS,
        provincia=True,
    ),
}
assert set(PROCESSORS) == set(KIND_DATASETS)


def process_update_std_data(
    config,
    normalized_dir=NORMALIZED_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=PROCESSED_DIR,
    type_format=TYPE_FORMAT,
):
    """Processes the standardized update parts; returns {<dataset>_update_pr: dataframe}."""
    config = load_config(config)
    normalized_dir = Path(normalized_dir)

    maps = load_mappings(mapping_dir)
    per_dataset = {}
    for part in plan_parts(config):
        logger.info("[%s] processing %s", part.dataset, part.std_name)
        std = read_df(normalized_dir, part.std_name, type_format)
        pr = PROCESSORS[part.kind](std, part.dataset, maps)
        per_dataset.setdefault(part.dataset, []).append(pr)

    dict_processed = {
        DATASETS[dataset].update_name: concat_keep_last(frames, name=dataset)
        for dataset, frames in per_dataset.items()
    }
    save_computed_dfs(
        dict_processed,
        local=True,
        type_format=type_format,
        path_saving=ensure_dir(out_dir),
    )
    logger.info("Processed update data saved in %s", out_dir)
    return dict_processed


if __name__ == "__main__":
    setup_logging()
    process_update_std_data(config_from_argv("Process the update standardized data."))
