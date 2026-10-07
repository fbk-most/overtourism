# SPDX-License-Identifier: Apache-2.0
"""Update data -> normalized -> processed, with the same standardize + process functions as the base build.

    aligned (adapter output) --standardize--> <part>_std   (update normalized dir)
    <part>_std               --process------> <part>_pr    (update processed dir)

A *part* is the set of sources that end up in the same files (see SourceSpec.part_name).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from data_preparation.utils.adapters import KIND_DATASETS, get_adapter
from data_preparation.utils.config import REFERENCES
from data_preparation.utils.datasets import (
    DATASETS,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_XALB_VALUE_COLS,
)
from data_preparation.utils.io import read_json
from data_preparation.utils.steps.process_std_data import (
    process_popolazione,
    process_presenze_ISPAT,
    process_strutture,
    process_vodafone,
)
from data_preparation.utils.steps.standardize_raw_data import (
    PRESENZE_APT_RENAMING,
    PRESENZE_PROV_RENAMING,
    standardize_popolazione_columns,
    standardize_presenze_columns,
    standardize_strutture_columns,
    standardize_vodafone_columns,
)
from data_preparation.utils.update.sources import fetch_bytes, fetch_geojson
from data_preparation.utils.update.spec import UpdateConfig

logger = logging.getLogger(__name__)

# presences dataset -> name of its value column
PRESENZE_OUTPUT_COL = {
    "presenze_alb": "presenze_alb",
    "presenze_extralb": "presenze_xalb",
}


# ------------------------------------------------------------------ parts
@dataclass(frozen=True)
class UpdatePart:
    name: str  # base name: <name>_std / <name>_pr
    dataset: str
    kind: str

    @property
    def std_name(self) -> str:
        return f"{self.name}_std"

    @property
    def pr_name(self) -> str:
        return f"{self.name}_pr"


def plan_parts(config: UpdateConfig) -> list:
    """The parts of the update, in config order. Sources with the same part name are stacked."""
    parts = {}
    for dataset in config.datasets:
        for src in config.sources[dataset]:
            kind = get_adapter(src.adapter).kind
            part = UpdatePart(src.part_name(dataset), dataset, kind)
            if parts.setdefault(part.name, part) != part:
                raise ValueError(
                    f"Sources of '{part.name}' have different kind/dataset: "
                    "give them a different `label`"
                )
    return list(parts.values())


# ------------------------------------------------------------------ references
@dataclass
class References:
    mapping_comuni: dict | None = None
    mapping_vodafone: dict | None = None
    mapping_apt: dict | None = None
    geojson: object | None = None

    def require(self, name):
        value = getattr(self, name)
        if value is None:
            raise RuntimeError(
                f"Reference '{name}' was not loaded (is the dataset selected?)"
            )
        return value


def _load_mapping(key, *, local_dir, mapping_dir) -> dict:
    """Mappings live in `mapping_dir` (shared with the base build). If the file is not there yet it is
    fetched (S3 or local_dir) and saved there, so there is a single copy."""
    target = Path(mapping_dir) / Path(key).name
    if target.exists():
        logger.info("Mapping %s read from %s", key, target)
        return read_json(target)
    logger.info("Mapping %s not in %s: fetching it", key, mapping_dir)
    return json.load(fetch_bytes(key, local_dir=local_dir, save_to=mapping_dir))


def load_references(
    config: UpdateConfig, datasets, *, mapping_dir, local_dir=None, raw_dir=None
) -> References:
    """Loads only the reference files needed by the selected datasets."""
    needed = {ref for d in datasets for ref in DATASETS[d].references}
    refs = References()
    for name in needed:
        key = REFERENCES[name]
        if name == "geojson":
            refs.geojson = fetch_geojson(key, local_dir=local_dir, save_to=raw_dir)
        else:
            setattr(
                refs,
                name,
                _load_mapping(key, local_dir=local_dir, mapping_dir=mapping_dir),
            )
    return refs


# ------------------------------------------------------------------ kind -> standardize
def _std_popolazione(df, dataset, refs):
    return standardize_popolazione_columns(df)


def _std_strutture(df, dataset, refs):
    return standardize_strutture_columns(df)


def _std_vodafone(df, dataset, refs):
    return standardize_vodafone_columns(df, refs.require("geojson"))


def _std_presenze_apt(df, dataset, refs):
    return standardize_presenze_columns(df, cols_renaming=PRESENZE_APT_RENAMING)


def _std_presenze_prov(df, dataset, refs):
    return standardize_presenze_columns(df, cols_renaming=PRESENZE_PROV_RENAMING)


STANDARDIZERS = {
    "popolazione": _std_popolazione,
    "strutture": _std_strutture,
    "vodafone": _std_vodafone,
    "presenze_apt": _std_presenze_apt,
    "presenze_prov": _std_presenze_prov,
}


# ------------------------------------------------------------------ kind -> process
def _pr_popolazione(df, dataset, refs):
    return process_popolazione(df, refs.require("mapping_comuni"))


def _pr_strutture(df, dataset, refs):
    return process_strutture(df, refs.require("mapping_comuni"))


def _pr_vodafone(df, dataset, refs):
    return process_vodafone(df, refs.require("mapping_vodafone"))


def _pr_presenze_apt(df, dataset, refs):
    """APT-level presences. Works for alberghiere and extra-alberghiere (value column from the dataset)."""
    out_col = PRESENZE_OUTPUT_COL[dataset]
    processed = process_presenze_ISPAT(
        df, refs.require("mapping_apt"), PRESENZE_ALB_VALUE_COLS, provincia=False
    )
    return (
        processed
        if out_col == "presenze_alb"
        else processed.rename(columns={"presenze_alb": out_col})
    )


def _pr_presenze_prov(df, dataset, refs):
    return process_presenze_ISPAT(
        df, refs.require("mapping_comuni"), PRESENZE_XALB_VALUE_COLS, provincia=True
    )


PROCESSORS = {
    "popolazione": _pr_popolazione,
    "strutture": _pr_strutture,
    "vodafone": _pr_vodafone,
    "presenze_apt": _pr_presenze_apt,
    "presenze_prov": _pr_presenze_prov,
}

assert set(STANDARDIZERS) == set(PROCESSORS) == set(KIND_DATASETS)


def standardize_aligned(
    kind: str, dataset: str, aligned: pd.DataFrame, refs: References
):
    return STANDARDIZERS[kind](aligned, dataset, refs)


def process_standardized(kind: str, dataset: str, std: pd.DataFrame, refs: References):
    return PROCESSORS[kind](std, dataset, refs)
