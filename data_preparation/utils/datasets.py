# SPDX-License-Identifier: Apache-2.0
"""Single source of truth about the datasets of the pipeline.

Everything that used to be repeated (dataset keys, processed file names, value columns used
for merging, which reference mappings each dataset needs, which datasets feed which phenomenon)
is defined here once.
"""

from dataclasses import dataclass

from utils.config import DATASET_FILES, PHENOMENA_FILES

# value columns of the processed dataframes
POPOLAZIONE_VALUE_COLS = ["popolazione"]
STRUTTURE_VALUE_COLS = [
    "tot_postiletto_non_conv",
    "tot_postiletto",
    "tot_strutture_non_conv",
    "tot_strutture",
]
VODAFONE_VALUE_COLS = ["presenze"]
PRESENZE_ALB_VALUE_COLS = ["presenze_alb"]
PRESENZE_XALB_VALUE_COLS = ["presenze_xalb"]

# ISPAT presences (alb / extralb): arrivals + presences per month, read from the raw files (no normalization).
# Files: Presenze/<arrivi|presenze>_<alb|exalb>_<year>.csv ; the base build downloads these years, the updates the others.
PRESENZE_FOLDER = "Presenze"
PRESENZE_BASE_YEARS = (2022, 2023)
PRESENZE_MEASURES = ("arrivi", "presenze")
# True: a stay that starts at the end of a month goes on in the next one (uses the previous month's arrivals and stay);
# False: every month is distributed using only its own arrivals and stay
PRESENZE_SPILL_OVER = True
PRESENZE_TAGS = {
    "presenze_alb": "alb",
    "presenze_extralb": "exalb",
}  # dataset -> tag in the file names

# reference files that a dataset may need to be standardized / processed
REF_MAPPING_COMUNI = "mapping_comuni"
REF_MAPPING_VODAFONE = "mapping_vodafone"
REF_MAPPING_APT = "mapping_apt"
REF_GEOJSON = "geojson"


@dataclass(frozen=True)
class DatasetSpec:
    name: str  # key used for selection, e.g. "presenze_alb"
    value_cols: tuple  # columns merged on (DATA, ID_COMUNE) when updating
    references: tuple  # reference files needed to process it
    std_name: str = (
        ""  # standardized dataframe name (step 1); "" = not normalized, processed from raw_data
    )
    processed_name: str = ""  # processed dataframe name (step 2)
    update_name: str = ""  # processed dataframe name in the yearly update

    @property
    def normalized(self) -> bool:
        return bool(self.std_name)


def _spec(name, value_cols, references, normalized=True):
    dataset_cfg = DATASET_FILES.get(name, {})
    return DatasetSpec(
        name=name,
        value_cols=tuple(value_cols),
        references=tuple(references),
        std_name=dataset_cfg.get("std", f"{name}_std" if normalized else ""),
        processed_name=dataset_cfg.get("processed", f"{name}_pr"),
        update_name=dataset_cfg.get("update", f"{name}_update_pr"),
    )


DATASETS = {
    spec.name: spec
    for spec in (
        _spec("popolazione", POPOLAZIONE_VALUE_COLS, [REF_MAPPING_COMUNI]),
        _spec("strutture", STRUTTURE_VALUE_COLS, [REF_MAPPING_COMUNI]),
        _spec("vodafone", VODAFONE_VALUE_COLS, [REF_MAPPING_VODAFONE, REF_GEOJSON]),
        _spec(
            "presenze_alb",
            PRESENZE_ALB_VALUE_COLS,
            [REF_MAPPING_APT, REF_MAPPING_COMUNI],
            normalized=False,
        ),
        _spec(
            "presenze_extralb",
            PRESENZE_XALB_VALUE_COLS,
            [REF_MAPPING_COMUNI],
            normalized=False,
        ),
    )
}
ALL_DATASETS = tuple(DATASETS)

# final phenomenon -> datasets that must ALL be updated for it to be recomputed
PHENOMENA = {name: frozenset(deps) for name, deps in PHENOMENA_FILES.items()}
PRESENZE_DATASETS = PHENOMENA["phen_presenze"]


def phenomena_to_recompute(selected) -> list:
    """Phenomena whose inputs are all among the selected datasets."""
    return [p for p, required in PHENOMENA.items() if required <= set(selected)]
