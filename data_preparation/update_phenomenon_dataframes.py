# SPDX-License-Identifier: Apache-2.0
"""
Yearly update of processed datasets (entry point).

    new raw files (names given in the update config)
        -> reader -> adapter (year-specific layout -> aligned layout)
        -> standardize -> process (in memory)
        -> merge with the existing processed data (new rows win on DATA + ID_COMUNE)
        -> Output/data/data_processed/ -> Output/data/final_data/

What is configured, and where:
  - config/settings.yaml          directories, file format, platform (shared with the base build)
  - config/updates/<round>.yaml   which datasets to update (listed / `enabled`), file names, readers,
                                  adapters and their parameters (year, column names...)
A new year with a new layout = a new adapter in utils/adapters/ + a new update yaml.

The current processed data (`paths.processed` in settings.yaml) must be in the same `type_format`.

Usage:
    python -m data_preparation.update_phenomenon_dataframes --config data_preparation/config/updates/update_2025.yaml
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from data_preparation.utils import config as cfg
from data_preparation.utils.adapters import get_adapter, validate_schema
from data_preparation.utils.datasets import DATASETS
from data_preparation.utils.io import ensure_dir, read_df, save_computed_dfs
from data_preparation.utils.steps.compute_phenomena import compute_phenomena
from data_preparation.utils.update.merge import merge_all_processed_dataframes
from data_preparation.utils.update.sources import read_source
from data_preparation.utils.update.spec import load_config
from data_preparation.utils.update.transform import (
    load_references,
    plan_parts,
    process_standardized,
    standardize_aligned,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# STEP 1: FETCH + ADAPT + STANDARDIZE (save raw + normalized)
# STEP 2: PROCESS (in memory)
# ---------------------------------------------------------------------------
def _references(config, selected):
    return load_references(
        config,
        selected,
        mapping_dir=ensure_dir(cfg.MAPPING_DIR),
        local_dir=cfg.LOCAL_SOURCE_DIR,
        raw_dir=ensure_dir(cfg.RAW_DIR),
    )


def standardize_updated_data(config, strict=True, refs=None):
    """Fetches, adapts and standardizes the sources of the datasets enabled in the config.

    Sources of the same part (see SourceSpec.part_name) are stacked; a source with a `label` is kept
    in its own part. Returns {<part>_std: dataframe}.
    """
    config = load_config(config)
    selected = config.datasets
    local_dir = cfg.LOCAL_SOURCE_DIR

    logger.info("Loading reference files for %s...", selected)
    refs = refs or _references(config, selected)

    frames = {}
    for dataset in selected:
        for src in config.sources[dataset]:
            logger.info("[%s] %s with adapter '%s'", dataset, src.file, src.adapter)
            raw = read_source(
                src.file,
                src.reader,
                src.reader_kwargs,
                local_dir=local_dir,
                raw_dir=cfg.RAW_DIR,
            )
            adapter = get_adapter(src.adapter)
            aligned = adapter.func(raw, **src.adapter_kwargs)
            validate_schema(aligned, adapter.kind, adapter.name, strict=strict)
            std = standardize_aligned(adapter.kind, dataset, aligned, refs)
            frames.setdefault(src.part_name(dataset), []).append(std)

    dict_std = {
        f"{name}_std": (
            parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)
        )
        for name, parts in frames.items()
    }
    save_computed_dfs(
        dict_std,
        local=True,
        type_format=cfg.TYPE_FORMAT,
        path_saving=ensure_dir(cfg.NORMALIZED_DIR),
    )
    return dict_std


def process_updated_data(config, dict_std, refs=None):
    """Processes standardized update frames in memory; returns {<part>_pr: dataframe}."""
    config = load_config(config)
    refs = refs or _references(config, config.datasets)
    dict_pr = {}
    for part in plan_parts(config):
        logger.info("[%s] processing %s", part.dataset, part.std_name)
        std = dict_std[part.std_name]
        dict_pr[part.pr_name] = process_standardized(part.kind, part.dataset, std, refs)
    return dict_pr


def _new_dfs_to_merge(config, dict_pr):
    """Stack source parts for each dataset into the frames to merge."""
    per_dataset, new_dfs = {}, {}
    for part in plan_parts(config):
        per_dataset.setdefault(part.dataset, []).append(dict_pr[part.pr_name])
    for dataset, frames in per_dataset.items():
        new_dfs[DATASETS[dataset].update_name] = (
            frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
        )
    return new_dfs


# ---------------------------------------------------------------------------
# COMPLETE UPDATE PIPELINE
# ---------------------------------------------------------------------------
def update_pipeline(config, strict=True):
    """Merge update data into shared processed data and refresh final phenomena."""
    config = load_config(config)
    selected = set(config.datasets)
    type_format = cfg.TYPE_FORMAT
    refs = _references(config, config.datasets)

    logger.info(
        "=== STEP 1: adapt + standardize update data (%s) ===", sorted(selected)
    )
    dict_std = standardize_updated_data(config, strict=strict, refs=refs)

    logger.info("=== STEP 2: process update data ===")
    dict_pr = process_updated_data(config, dict_std, refs=refs)
    new_dfs = _new_dfs_to_merge(config, dict_pr)

    logger.info(
        "=== STEP 3a: read current processed data from %s ===", cfg.PROCESSED_DIR
    )
    old_dfs = {
        spec.processed_name: read_df(
            cfg.PROCESSED_DIR, spec.processed_name, type_format
        )
        for spec in DATASETS.values()
    }

    logger.info("=== STEP 3b: merge processed data ===")
    merged_dfs = merge_all_processed_dataframes(old_dfs, new_dfs)
    save_computed_dfs(
        merged_dfs,
        local=True,
        type_format=type_format,
        path_saving=ensure_dir(cfg.PROCESSED_DIR),
    )
    logger.info("=== STEP 4: recompute final phenomena in %s ===", cfg.FINAL_DIR)
    compute_phenomena(
        processed_dir=cfg.PROCESSED_DIR,
        out_dir=ensure_dir(cfg.FINAL_DIR),
        type_format=type_format,
        local=True,
    )
    logger.info("=== UPDATE COMPLETED ===")
    return merged_dfs


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Yearly update of the processed datasets.")
    p.add_argument(
        "--config", required=True, type=Path, help="update config (.yaml/.yml/.json)"
    )
    p.add_argument(
        "--no-strict",
        action="store_true",
        help="only warn on adapter schema mismatches",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    cfg.setup_logging()
    args = _parse_args(argv)
    update_pipeline(args.config, strict=not args.no_strict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
