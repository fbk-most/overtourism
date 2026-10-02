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
import geopandas as geopd
import pandas as pd

from data_preparation.utils.utils import (
    get_mapping, get_s3, save_computed_dfs
)
from data_preparation.utils.common import (
    PROCESSED_DIR, OUTPUT_DIR,
    _read_grouped_presenze_tsv, check_output_dir, normalize_id_comune,
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

logging.basicConfig(level=logging.INFO)

ALL_DATASETS_KEYS = ["popolazione", "strutture", "vodafone", "presenze_alb", "presenze_extralb"]
PROCESSED_OLD_KEYS = ["popolazione_pr", "strutture_pr", "vodafone_pr", "presenze_alb_pr", "presenze_extralb_pr"]
PRESENZE_DATASETS_KEYS = {"vodafone", "presenze_alb", "presenze_extralb"}

MERGED_PROCESSED_DIR = OUTPUT_DIR / "data_update" / "merged_processed"
UPDATE_PROCESSED_DIR = OUTPUT_DIR / "data_update" / "data_processed"
FINAL_UPDATE_DIR = OUTPUT_DIR / "data_update" / "final_phenomena"

UPDATE_S3_OBJECTS = {
    "popolazione": "popolazione_2026_ISPAT.csv",
    "vodafone": "vodafone_attendences_new.csv",
    "strutture_2024": "strutture_annuario_2024.ods",
    "strutture_2025": "numero_strutture_ISPAT_2025.xlsx",
    "presenze_alb_2025": "presenze_alb_2025.csv",
    "presenze_xalb_2025_apt": "presenze_xalb_2025.csv",
    "presenze_xalb_2025_prov": "presenze_xalb_2025_prov.csv",
    "comuni_trentino_geojson": "TRENTINO-comuni_Vodafone_2023.geojson",
}

# ---------------------------------------------------------------------------
# STANDARDIZATION + PROCESSING OF UPDATE DATA
# ---------------------------------------------------------------------------


## Popolazione
def standardize_and_process_popolazione_2025(df, mapping_comuni):
    """Standardization function for popolazione. It is computed as the arithmetic mean between population at 01/01/2025 and 01/01/2026."""
    df = align_data_popolazione_2025(df)
    # standardization and process
    return process_popolazione(standardize_popolazione_columns(df), mapping_comuni)


## Strutture
def standardize_and_process_strutture(df, mapping_comuni, comune_col="Comune", year=2025):
    """Adapts the strutture to the "standard" one in order to reuse standardize_strutture_columns() + process_strutture()"""
    df = align_data_strutture(df, comune_col= comune_col, year=year)
    return process_strutture(standardize_strutture_columns(df), mapping_comuni)


## Vodafone
def standardize_and_process_vodafone_2025(df, mapping_vodafone, geojson):
    """Adapt the new Vodafone data using the dedicated functions."""
    return process_vodafone(standardize_vodafone_columns(df, geojson), mapping_vodafone)


## Presenze
def standardize_and_process_presenze_2025_apt(df, apts, mapping_apt, output_col="presenze_alb"):
    """
    Standardize and process presenze data at APT granularity.
    Can be used for both alberghiero (output_col="presenze_alb") 
    and extra-alberghiero (output_col="presenze_xalb").
    """
    long_df = align_presenze_ispat_apts(df, apts, 2025)
    std = standardize_presenze_columns(
        long_df, 
        cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"}
    )
    processed = process_presenze_ISPAT(std, mapping_apt, PRESENZE_ALB_VALUE_COLS, provincia=False)
    
    if output_col != "presenze_alb":
        return processed.rename(columns={"presenze_alb": output_col})
        
    return processed

def standardize_and_process_presenze_extralb_2025_prov(df, mapping_comuni):
    """Standardize the provincial extra-alberghiero dataset."""
    df_alb_xalb_prov = align_presenze_ispat_prov(df)
    std = standardize_presenze_columns(df_alb_xalb_prov,cols_renaming={"Presenze alberghi": "presenze_alb","Presenze extra-alberghi": "presenze_xalb",})
    return process_presenze_ISPAT(std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True)

# ---------------------------------------------------------------------------
# DOWNLOAD + STANDARDIZE + PROCESS UPDATE
# ---------------------------------------------------------------------------

def process_updated_data(out_dir=UPDATE_PROCESSED_DIR, type_format="csv", datasets=None):
    """Download, standardize and process only the requested update-source datasets.
    datasets: subset of ALL_DATASETS, default = all."""
    ## download mapping and geojson data 
    datasets = set(datasets) if datasets else set(ALL_DATASETS_KEYS)
    if datasets - set(ALL_DATASETS_KEYS):
        raise ValueError(f"Unknown dataset(s): {sorted(datasets - set(ALL_DATASETS_KEYS))}. Valid: {ALL_DATASETS_KEYS}")

    check_output_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Loading mappings and reference GeoJSON...")

    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_apt = get_mapping("map_comuni_into_apt.json")
    geojson = geopd.read_file(get_s3(UPDATE_S3_OBJECTS["comuni_trentino_geojson"]))
    dict_dfs = {}

    if "popolazione" in datasets:
        logging.info("Downloading and processing popolazione updated dataset...")
        popolazione_raw = pd.read_csv(get_s3(UPDATE_S3_OBJECTS["popolazione"])) #  download from ISPAT
        dict_dfs["popolazione_25_pr"] = standardize_and_process_popolazione_2025(popolazione_raw, mapping_comuni)

    if "strutture" in datasets:
        logging.info("Downloading and processing strutture updated datasets 2024 and 2025...")
        strutture_24_raw = pd.read_excel(get_s3(UPDATE_S3_OBJECTS["strutture_2024"]), engine="odf")    ## TODO: upload the version xlsx for consistency
        strutture_25_raw = pd.read_excel(get_s3(UPDATE_S3_OBJECTS["strutture_2025"]), header=[0, 1])
        dict_dfs["strutture_24_pr"] = standardize_and_process_strutture(strutture_24_raw, mapping_comuni, comune_col="Comuni", year=2024)
        dict_dfs["strutture_25_pr"] = standardize_and_process_strutture(strutture_25_raw, mapping_comuni, comune_col="Comune", year=2025)

    if "vodafone" in datasets:
        logging.info("Downloading and processing vodafone updated dataset...")
        vodafone_raw = pd.read_csv(get_s3(UPDATE_S3_OBJECTS["vodafone"]))
        dict_dfs["vodafone_25_pr"] = standardize_and_process_vodafone_2025(vodafone_raw, mapping_vodafone, geojson)

    if "presenze_alb" in datasets:
        logging.info("Downloading and processing presenze alberghiere updated dataset..")
        alb_buffer = get_s3(UPDATE_S3_OBJECTS["presenze_alb_2025"])
        raw_alb = pd.read_csv(alb_buffer, sep="\t", header=None, skiprows=2, dtype=str)
        apts = [x.strip() for x in alb_buffer.getvalue().decode("utf-8").splitlines()[0].split("\t")]
        dict_dfs["presenze_alb_25_pr"] = standardize_and_process_presenze_alb_2025(raw_alb, apts, mapping_apt)

    if "presenze_extralb" in datasets:
        logging.info("Downloading and processing presenze extralberghiere dataset...")
        xalb_apt_buffer = get_s3(UPDATE_S3_OBJECTS["presenze_xalb_2025_apt"])
        raw_xalb_apt = pd.read_csv(xalb_apt_buffer, sep="\t", header=None, skiprows=2, dtype=str)
        apts_xalb = [x.strip() for x in xalb_apt_buffer.getvalue().decode("utf-8").splitlines()[0].split("\t")]
        raw_xalb_prov = _read_grouped_presenze_tsv(get_s3(UPDATE_S3_OBJECTS["presenze_xalb_2025_prov"]))
        dict_dfs["presenze_extralb_25_apt_pr"] = standardize_and_process_presenze_extralb_2025_apt(raw_xalb_apt, apts_xalb, mapping_apt)
        dict_dfs["presenze_extralb_25_pr"] = standardize_and_process_presenze_extralb_2025_prov(raw_xalb_prov, mapping_comuni)

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

def _make_hashable(value):
    """Canonical representation used exclusively for deduplication."""
    value = normalize_id_comune(value)

    if isinstance(value, tuple):
        return tuple(str(x).zfill(6) for x in value)

    if pd.isna(value):
        return value

    return str(value).zfill(6)


def merge_update(df_old, df_new, value_cols):
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

def merge_dataframes_processed(old_dfs: dict, new_dfs: dict) -> dict:
    """Merge existing processed data with the update.
    Returns only the dataframes that were actually updated."""
    merged = {}
    if "popolazione_25_pr" in new_dfs:
        merged["popolazione_pr"] = merge_update(
            old_dfs["popolazione_pr"], new_dfs["popolazione_25_pr"], ["popolazione"]
        )

    if "strutture_24_pr" in new_dfs and "strutture_25_pr" in new_dfs:
        strutture = merge_update(
            old_dfs["strutture_pr"],
            new_dfs["strutture_24_pr"],
            ["tot_postiletto_non_conv", "tot_postiletto", "tot_strutture_non_conv", "tot_strutture"],
        )
        merged["strutture_pr"] = merge_update(
            strutture,
            new_dfs["strutture_25_pr"],
            ["tot_postiletto_non_conv", "tot_postiletto", "tot_strutture_non_conv", "tot_strutture"],
        )

    if "vodafone_25_pr" in new_dfs:
        merged["vodafone_pr"] = merge_update(
            old_dfs["vodafone_pr"], new_dfs["vodafone_25_pr"], ["presenze"]
        )

    if "presenze_alb_25_pr" in new_dfs:
        merged["presenze_alb_pr"] = merge_update(
            old_dfs["presenze_alb_pr"], new_dfs["presenze_alb_25_pr"], ["presenze_alb"]
        )

    if "presenze_extralb_25_pr" in new_dfs:
        merged["presenze_extralb_pr"] = merge_update(
            old_dfs["presenze_extralb_pr"], new_dfs["presenze_extralb_25_pr"], ["presenze_xalb"]
        )

    if "presenze_extralb_25_apt_pr" in new_dfs:
        # Different granularity; keep as an update artifact.
        merged["presenze_extralb_25_apt_pr"] = new_dfs["presenze_extralb_25_apt_pr"]

    return merged

# ---------------------------------------------------------------------------
# COMPLETE UPDATE PIPELINE
# ---------------------------------------------------------------------------
def update_pipeline(
    processed_dir=PROCESSED_DIR,
    final_dir=FINAL_UPDATE_DIR,
    update_dir=UPDATE_PROCESSED_DIR,
    merged_dir=MERGED_PROCESSED_DIR,
    type_format="csv",
    datasets=None,
):
    """Complete update pipeline.
    Steps:
        1. download + standardize + process new data
        2. read current processed data
        3. merge old/new, with new data winning overlaps
        4. recompute final phenomena (if all required datasets are updated)
    datasets: subset of ALL_DATASETS to actually update; default None updates all."""

    selected_datasets = set(datasets) if datasets else set(ALL_DATASETS_KEYS)

    presenze_intersection = selected_datasets.intersection(PRESENZE_DATASETS_KEYS)
    if presenze_intersection and presenze_intersection != PRESENZE_DATASETS_KEYS:
        missing = PRESENZE_DATASETS_KEYS - presenze_intersection
        logging.warning(
            f"All datasets of presenze {sorted(PRESENZE_DATASETS_KEYS)} has are needed to compute updated 'phen_presenze'. Missing: {sorted(missing)}"
        )

    logging.info("=== STEP 1: standardize/process update data (%s) ===", selected_datasets)
    new_dfs = process_updated_data(out_dir=update_dir, type_format=type_format, datasets=selected_datasets)

    logging.info("=== STEP 2: read current processed data ===")
    processed_dfs_old = {name: read_df(processed_dir, name, type_format) for name in PROCESSED_OLD_KEYS}

    logging.info("=== STEP 3: merge processed data ===")
    merged_dfs = merge_dataframes_processed(processed_dfs_old, new_dfs)

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
    update_pipeline(type_format="parquet")