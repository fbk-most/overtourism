# SPDX-License-Identifier: Apache-2.0
"""
Update procedure for the v2 data-preparation pipeline.

Pipeline:
    Takes existing processed data
    + new raw data from S3
        -> standardize new raw data
        -> process new data
        -> merge (new rows used in case of DATA + ID_COMUNE overlaps)
        -> compute final phenomena

Every step can be run on a SUBSET of phenomena: the phenomena not selected are left untouched, reusing the data already in `processed_dir`.
"""

import logging
import pandas as pd

from data_preparation.utils.utils import (
    save_computed_dfs
)
from data_preparation.utils.common import (
    PROCESSED_DIR, OUTPUT_DIR,
    check_output_dir, _make_hashable,
    read_df, standard_ordering_cols,
)
from data_preparation.standardize_raw_data import (
    standardize_popolazione_columns, standardize_strutture_columns,
    standardize_vodafone_columns, standardize_presenze_columns,
)
from data_preparation.process_std_data import (
    PRESENZE_ALB_VALUE_COLS, PRESENZE_XALB_VALUE_COLS,
    process_popolazione, process_presenze_ISPAT, process_strutture,
    process_vodafone,
)
from data_preparation.gen_base_phenomenon_dataframes import (
    calculate_phenomena,
)
from data_preparation.align_data_for_standardization import (
    align_data_popolazione_2025, 
    align_data_strutture, 
    align_presenze_ispat_apts, 
    align_presenze_ispat_prov
)
from data_preparation.utils.fetch_new_data import (
    fetch_reference_maps, fetch_raw_popolazione, fetch_raw_strutture,
    fetch_raw_vodafone, fetch_raw_presenze_alb, fetch_raw_presenze_extralb
)

logging.basicConfig(level=logging.INFO)

ALL_DATASETS_KEYS = ["popolazione", "strutture", "vodafone", "presenze_alb", "presenze_extralb"]
PROCESSED_OLD_KEYS = ["popolazione_pr", "strutture_pr", "vodafone_pr", "presenze_alb_pr", "presenze_extralb_pr"]
PRESENZE_DATASETS_KEYS = {"vodafone", "presenze_alb", "presenze_extralb"}

MERGED_PROCESSED_DIR = OUTPUT_DIR / "data_update" / "merged_processed"
UPDATE_PROCESSED_DIR = OUTPUT_DIR / "data_update" / "data_processed"
FINAL_UPDATE_DIR = OUTPUT_DIR / "data_update" / "final_phenomena"

EXPECTED_COLS_POPOLAZIONE = ["comune", "popolazione", "anno"]
EXPECTED_COLS_STRUTTURE = [
    "comune", "anno", "alberghieri strutture", "alberghieri posti_letto", 
    "extra alb. Strutture", "extra alb. Posti_letto", "tot convenzionali strutture", 
    "tot convenzionali posti_letto", "COMPLESSIVO numero", "COMPLESSIVO posti_letto", 
    "all. privati numero", "all. privati posti_letto"
]
EXPECTED_COLS_VODAFONE_RAW = ["locId", "date", "value"]
EXPECTED_COLS_PRESENZE_APT = ["Ambito", "Anno", "Mese", "Presenze"]
EXPECTED_COLS_PRESENZE_PROV = ["Anno", "Mese", "Presenze alberghi", "Presenze extra-alberghi"]


# ---------------------------------------------------------------------------
# COMPATIBILITY CHECK
# ---------------------------------------------------------------------------
def check_cols_compatibility(df: pd.DataFrame, expected_cols: list[str], func_name: str) -> bool:
    """Checks if all expected columns are present within the DataFrame columns."""
    missing_cols = sorted(set(expected_cols) - set(df.columns))
    if missing_cols:
        logging.warning(
            f"Mismatch in '{func_name}'! Missing columns: {missing_cols}. "
            f"Please verify that the data alignment function is correct."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# STANDARDIZATION + PROCESSING OF UPDATE DATA
# ---------------------------------------------------------------------------

## Popolazione
def standardize_and_process_popolazione_updated(df, mapping_comuni):
    """Standardization function for popolazione."""
    df = align_data_popolazione_2025(df)
    check_cols_compatibility(df, expected_cols=EXPECTED_COLS_POPOLAZIONE, func_name="align_data_popolazione_2025")
    return process_popolazione(standardize_popolazione_columns(df), mapping_comuni)


## Strutture
def standardize_and_process_strutture_updated(df, mapping_comuni, comune_col="Comune", year=2025):
    """Adapts the strutture to the standard format."""
    df = align_data_strutture(df, comune_col=comune_col, year=year)
    check_cols_compatibility(df, expected_cols=EXPECTED_COLS_STRUTTURE, func_name="align_data_strutture")
    return process_strutture(standardize_strutture_columns(df), mapping_comuni)


## Vodafone
def standardize_and_process_vodafone_updated(df, mapping_vodafone, geojson):
    """Adapt the new Vodafone data using the dedicated functions."""
    check_cols_compatibility(df, expected_cols=EXPECTED_COLS_VODAFONE_RAW, func_name="fetch_raw_vodafone")
    return process_vodafone(standardize_vodafone_columns(df, geojson), mapping_vodafone)


## Presenze APT
def standardize_and_process_presenze_apt_updated(df, apts, mapping_apt, output_col="presenze_alb"):
    """
    Standardize and process presenze data at APT granularity.
    Can be used for both alberghiero (output_col="presenze_alb") 
    and extra-alberghiero (output_col="presenze_xalb").
    """
    long_df = align_presenze_ispat_apts(df, apts, 2025)
    check_cols_compatibility(long_df, expected_cols=EXPECTED_COLS_PRESENZE_APT, func_name="align_presenze_ispat_apts")
    std = standardize_presenze_columns(long_df, cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"})
    processed = process_presenze_ISPAT(std, mapping_apt, PRESENZE_ALB_VALUE_COLS, provincia=False)
    
    if output_col != "presenze_alb":
        return processed.rename(columns={"presenze_alb": output_col})
        
    return processed

## Presenze Provinciali
def standardize_and_process_presenze_extralb_prov_updated(df, mapping_comuni):
    """Standardize the provincial extra-alberghiero dataset."""
    df_alb_xalb_prov = align_presenze_ispat_prov(df)
    check_cols_compatibility(df_alb_xalb_prov, expected_cols=EXPECTED_COLS_PRESENZE_PROV, func_name="align_presenze_ispat_prov")
    std = standardize_presenze_columns(df_alb_xalb_prov,cols_renaming={"Presenze alberghi": "presenze_alb","Presenze extra-alberghi": "presenze_xalb",})
    return process_presenze_ISPAT(std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True)


# ---------------------------------------------------------------------------
# DOWNLOAD + STANDARDIZE + PROCESS UPDATE
# ---------------------------------------------------------------------------

def process_updated_data(out_dir=UPDATE_PROCESSED_DIR, type_format="csv", datasets=None):
    """Download, standardize and process only the requested update-source datasets.
    datasets: subset of ALL_DATASETS, default = all."""
    datasets = set(datasets) if datasets else set(ALL_DATASETS_KEYS)
    if datasets - set(ALL_DATASETS_KEYS):
        raise ValueError(f"Unknown dataset(s): {sorted(datasets - set(ALL_DATASETS_KEYS))}. Valid: {ALL_DATASETS_KEYS}")

    check_output_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Loading mappings and reference GeoJSON...")
    mapping_vodafone, mapping_comuni, mapping_apt, geojson = fetch_reference_maps()

    dict_dfs = {}

    if "popolazione" in datasets:
        logging.info("Downloading and processing popolazione updated dataset...")
        popolazione_raw = fetch_raw_popolazione()
        dict_dfs["popolazione_update_pr"] = standardize_and_process_popolazione_updated(popolazione_raw, mapping_comuni)

    if "strutture" in datasets:
        logging.info("Downloading and processing strutture updated datasets...")
        strutture_24_raw, strutture_25_raw = fetch_raw_strutture()
        
        df_24 = standardize_and_process_strutture_updated(strutture_24_raw, mapping_comuni, comune_col="Comuni", year=2024)
        df_25 = standardize_and_process_strutture_updated(strutture_25_raw, mapping_comuni, comune_col="Comune", year=2025)
        ## Concats the years 
        dict_dfs["strutture_update_pr"] = pd.concat([df_24, df_25], ignore_index=True)

    if "vodafone" in datasets:
        logging.info("Downloading and processing vodafone updated dataset...")
        vodafone_raw = fetch_raw_vodafone()
        dict_dfs["vodafone_update_pr"] = standardize_and_process_vodafone_updated(vodafone_raw, mapping_vodafone, geojson)

    if "presenze_alb" in datasets:
        logging.info("Downloading and processing presenze alberghiere updated dataset..")
        raw_alb, apts = fetch_raw_presenze_alb()
        dict_dfs["presenze_alb_update_pr"] = standardize_and_process_presenze_apt_updated(raw_alb, apts, mapping_apt)

    if "presenze_extralb" in datasets:
        logging.info("Downloading and processing presenze extralberghiere dataset...")
        raw_xalb_apt, apts_xalb, raw_xalb_prov = fetch_raw_presenze_extralb()
        dict_dfs["presenze_extralb_25_apt_pr"] = standardize_and_process_presenze_apt_updated(raw_xalb_apt, apts_xalb, mapping_apt, output_col="presenze_xalb")
        dict_dfs["presenze_extralb_update_pr"] = standardize_and_process_presenze_extralb_prov_updated(raw_xalb_prov, mapping_comuni)

    save_computed_dfs(
        dict_dfs,
        local=True,
        type_format=type_format,
        path_saving=out_dir,
    )

    logging.info("Update processed data saved in %s", out_dir)
    return dict_dfs


# ---------------------------------------------------------------------------
# MERGE
# ---------------------------------------------------------------------------

def merge_new_pr_dataframe(df_old, df_new, value_cols):
    """Merges old and new: checks the columns and updates the data if there is some intersection.
    If common_cols is set to None, df_old.columns are used as reference
    Merge using DATA + ID_COMUNE (via _make_hashable, to deal with ID_COMUNE lists)"""
    required = {"DATA", "ID_COMUNE", *value_cols}    
    ## si presume questi assert passino dopo la standardizzazione
    assert required.issubset(df_old.columns), "Columns required not all found in old DF"
    assert required.issubset(df_new.columns), "Columns required not all found in new DF"

    cols = ["DATA", "ID_COMUNE", *value_cols]
    merged = pd.concat(
        [df_old[cols], df_new[cols]], ignore_index=True
    ).copy()

    merged["_ID_KEY"] = merged["ID_COMUNE"].map(_make_hashable) # we use tuple to avoid type problems 
    merged = (
        merged.drop_duplicates(
            subset=["DATA", "_ID_KEY"], keep="last"
        )
        .sort_values(["DATA", "_ID_KEY"])
        .drop(columns="_ID_KEY")
        .reset_index(drop=True)
    )    # print(merged["ID_COMUNE"].apply(type).value_counts())
    return standard_ordering_cols(merged)

def merge_all_processed_dataframes(old_dfs: dict, new_dfs: dict) -> dict:
    """Merge existing processed data with the update.
    Returns only the dataframes that were actually updated."""
    merged = {}
    if "popolazione_update_pr" in new_dfs:
        merged["popolazione_pr"] = merge_new_pr_dataframe(
            old_dfs["popolazione_pr"], new_dfs["popolazione_update_pr"], ["popolazione"]
        )

    if "strutture_update_pr" in new_dfs:
            merged["strutture_pr"] = merge_new_pr_dataframe(
                old_dfs["strutture_pr"],
                new_dfs["strutture_update_pr"],
                ["tot_postiletto_non_conv", "tot_postiletto", "tot_strutture_non_conv", "tot_strutture"],
            )
    if "vodafone_update_pr" in new_dfs:
        merged["vodafone_pr"] = merge_new_pr_dataframe(
            old_dfs["vodafone_pr"], new_dfs["vodafone_update_pr"], ["presenze"]
        )

    if "presenze_alb_update_pr" in new_dfs:
        merged["presenze_alb_pr"] = merge_new_pr_dataframe(
            old_dfs["presenze_alb_pr"], new_dfs["presenze_alb_update_pr"], ["presenze_alb"]
        )

    if "presenze_extralb_update_pr" in new_dfs:
        merged["presenze_extralb_pr"] = merge_new_pr_dataframe(
            old_dfs["presenze_extralb_pr"], new_dfs["presenze_extralb_update_pr"], ["presenze_xalb"]
        )

    if "presenze_extralb_25_apt_pr" in new_dfs:
        # Different granularity; keep as an update artifact.
        merged["presenze_extralb_25_apt_pr"] = new_dfs["presenze_extralb_25_apt_pr"]

    return merged


# ---------------------------------------------------------------------------
# COMPLETE UPDATE PIPELINE
# ---------------------------------------------------------------------------

def update_pipeline_phen_computation(
    processed_dir=PROCESSED_DIR,
    final_dir=FINAL_UPDATE_DIR,
    update_dir=UPDATE_PROCESSED_DIR,
    merged_dir=MERGED_PROCESSED_DIR,
    type_format="csv",
    datasets=None,
):
    """Complete update pipeline."""
    selected_datasets = set(datasets) if datasets else set(ALL_DATASETS_KEYS)

    presenze_intersection = selected_datasets.intersection(PRESENZE_DATASETS_KEYS)
    if presenze_intersection and presenze_intersection != PRESENZE_DATASETS_KEYS:
        missing = PRESENZE_DATASETS_KEYS - presenze_intersection
        logging.warning(
            f"All datasets of presenze {sorted(PRESENZE_DATASETS_KEYS)} are needed to compute updated 'phen_presenze'. Missing: {sorted(missing)}"
        )

    logging.info("=== STEP 1: standardize/process update data (%s) ===", selected_datasets)
    new_dfs = process_updated_data(out_dir=update_dir, type_format=type_format, datasets=selected_datasets)

    logging.info("=== STEP 2: read current processed data ===")
    processed_dfs_old = {name: read_df(processed_dir, name, type_format) for name in PROCESSED_OLD_KEYS}

    logging.info("=== STEP 3: merge processed data ===")
    merged_dfs = merge_all_processed_dataframes(processed_dfs_old, new_dfs)

    check_output_dir(merged_dir)
    merged_dir.mkdir(parents=True, exist_ok=True)

    save_computed_dfs(
        merged_dfs,
        local=True,
        type_format=type_format,
        path_saving=merged_dir,
    )

    logging.info("=== STEP 4: recompute final phenomena ===")

    # Combine old baseline data with newly merged data for full context
    full_processed = {**processed_dfs_old, **merged_dfs}
    all_phenomena = calculate_phenomena(
        full_processed["popolazione_pr"],
        full_processed["strutture_pr"],
        full_processed["vodafone_pr"],
        full_processed["presenze_alb_pr"],
        full_processed["presenze_extralb_pr"],
    )

    # Filter and save only the phenomena affected by the selected update datasets
    phenomena_to_save = {}
    if "popolazione" in selected_datasets:
        phenomena_to_save["phen_popolazione"] = all_phenomena["phen_popolazione"]

    if "strutture" in selected_datasets:
        phenomena_to_save["phen_strutture"] = all_phenomena["phen_strutture"]

    if PRESENZE_DATASETS_KEYS.issubset(selected_datasets):
        phenomena_to_save["phen_presenze"] = all_phenomena["phen_presenze"]

    if phenomena_to_save:
        check_output_dir(final_dir)
        final_dir.mkdir(parents=True, exist_ok=True)

        save_computed_dfs(
            phenomena_to_save,
            local=True,
            type_format=type_format,
            path_saving=final_dir,
        )
    else:
        logging.warning("No extra phenomena saved.")

    logging.info("=== UPDATE COMPLETED ===")
    return merged_dfs


if __name__ == "__main__":
    update_pipeline_phen_computation(type_format="parquet")