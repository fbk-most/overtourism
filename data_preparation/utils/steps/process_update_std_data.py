# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 (update) - Processing of the update standardized data.

Input : Output/data/normalized/     (<part>_std, written by standardize_update_raw_data)
        Output/data/raw_data/       (ISPAT arrivals / presences of alb and extralb: not normalized)
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

from utils.adapters import KIND_DATASETS
from utils.cleaning import concat_keep_last
from utils.config import (
    MAPPING_DIR,
    NORMALIZED_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    TYPE_FORMAT,
    setup_logging,
)
from utils.datasets import (
    DATASETS,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_MEASURES,
    PRESENZE_TAGS,
    PRESENZE_XALB_VALUE_COLS,
)
from utils.io import ensure_dir, read_df, save_computed_dfs
from utils.steps.process_std_data import (
    BEDS_ALB_COL,
    BEDS_XALB_COL,
    load_mappings,
    presenze_alb_area_ids,
    presenze_exalb_area_ids,
    presenze_files,
    process_beds,
    process_popolazione,
    process_presenze_stay,
    process_strutture,
    process_vodafone,
    read_strutture_std,
)
from utils.update.spec import config_from_argv, load_config, plan_parts

logger = logging.getLogger(__name__)

# kind -> processing of the normalized parts (same functions of the base build).
# `strutture` = processed strutture (beds for the split of the vodafone areas)
PROCESSORS = {
    "popolazione": lambda df, maps, strutture: process_popolazione(
        df, maps["mapping_comuni"]
    ),
    "strutture": lambda df, maps, strutture: process_strutture(
        df, maps["mapping_comuni"]
    ),
    "vodafone": lambda df, maps, strutture: process_vodafone(
        df, maps["mapping_vodafone"], strutture
    ),
}
# the ISPAT presences (alb / extralb) are not normalized: processed from the raw files, see below
assert set(PROCESSORS) | {"presenze_raw"} == set(KIND_DATASETS)

PROCESS_ORDER = (
    "popolazione",
    "strutture",
    "vodafone",
    "presenze_alb",
    "presenze_extralb",
)


def _processed_reference(dataset, done, processed_dir, type_format):
    """Processed frame of `dataset`: base `<dataset>_pr` (if any) updated by this run."""
    frames = []
    try:
        frames.append(
            read_df(processed_dir, DATASETS[dataset].processed_name, type_format)
        )
    except FileNotFoundError:
        pass
    if dataset in done:
        frames.append(done[dataset])
    if not frames:
        logger.warning("[%s] no processed data available: uniform split", dataset)
        return None
    return concat_keep_last(frames, name=f"{dataset} reference")


def _process_presenze(dataset, config, maps, beds, raw_dir):
    """alb / extralb of the update: arrivals + presences files listed in the config -> comune x day."""
    tag = PRESENZE_TAGS[dataset]
    files, years = {}, set()
    for src in config.sources[dataset]:
        kw = src.adapter_kwargs
        files[(kw["measure"], int(kw["year"]))] = Path(raw_dir) / Path(src.file).name
        years.add(int(kw["year"]))
    for y in years:
        missing = [m for m in PRESENZE_MEASURES if (m, y) not in files]
        if missing:
            raise ValueError(
                f"[{dataset}] year {y}: missing {missing} in the update config"
            )
    # files of the year before (e.g. from the previous update / the base build), if already downloaded
    ctx = min(years) - 1
    files = {**presenze_files(raw_dir, tag, [ctx]), **files}
    if dataset == "presenze_alb":
        area_ids, bed_col = presenze_alb_area_ids(maps["mapping_apt"]), BEDS_ALB_COL
    else:
        area_ids, bed_col = (
            presenze_exalb_area_ids(maps["mapping_comuni"]),
            BEDS_XALB_COL,
        )
    return process_presenze_stay(
        files,
        "alb" if dataset == "presenze_alb" else "exalb",
        sorted(years),
        area_ids,
        beds,
        bed_col=bed_col,
        out_col=DATASETS[dataset].value_cols[0],
    )


def process_update_std_data(
    config,
    normalized_dir=NORMALIZED_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=PROCESSED_DIR,
    type_format=TYPE_FORMAT,
    raw_dir=RAW_DIR,
):
    """Processes the standardized update parts; returns {<dataset>_update_pr: dataframe}."""
    config = load_config(config)
    normalized_dir = Path(normalized_dir)

    maps = load_mappings(mapping_dir)
    parts = plan_parts(config)
    done = {}  # dataset -> stacked processed frame, filled following PROCESS_ORDER
    beds = None
    for dataset in PROCESS_ORDER:
        if dataset in PRESENZE_TAGS:
            if dataset not in config.datasets:
                continue
            if beds is None:  # beds of every normalized strutture file (base + updates)
                beds = process_beds(
                    read_strutture_std(normalized_dir, type_format),
                    maps["mapping_comuni"],
                )
            logger.info("[%s] processing the raw arrivals / presences", dataset)
            done[dataset] = _process_presenze(dataset, config, maps, beds, raw_dir)
            continue
        frames = []
        for part in (p for p in parts if p.dataset == dataset):
            logger.info("[%s] processing %s", part.dataset, part.std_name)
            std = read_df(normalized_dir, part.std_name, type_format)
            strutture = (
                _processed_reference("strutture", done, out_dir, type_format)
                if dataset == "vodafone"
                else None
            )
            frames.append(PROCESSORS[part.kind](std, maps, strutture))
        if frames:
            done[dataset] = concat_keep_last(frames, name=dataset)

    dict_processed = {DATASETS[d].update_name: df for d, df in done.items()}
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
