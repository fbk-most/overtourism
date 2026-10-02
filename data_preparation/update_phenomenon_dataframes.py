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
from pathlib import Path
import geopandas as geopd
import pandas as pd

from data_preparation.utils.utils import get_mapping, get_s3, save_computed_dfs
from data_preparation.utils.common import (
    _read_grouped_presenze_tsv,
    _remove_unnamed,
    PROCESSED_DIR, OUTPUT_DIR, check_output_dir, normalize_id_comune,
    read_df, standard_ordering_cols,
)
from data_preparation.standardize_raw_data import (
    standardize_popolazione_columns, standardize_strutture_columns,
    standardize_vodafone_columns, standardize_presenze_columns,
)
from data_preparation.process_data import (
    PRESENZE_ALB_VALUE_COLS, PRESENZE_XALB_VALUE_COLS,
    process_popolazione, process_presenze_ISPAT, process_strutture,
    process_vodafone,
)
from data_preparation.gen_base_phenomenon_dataframes import (
    calculate_phenomena,
)

logging.basicConfig(level=logging.INFO)

ALL_DATASETS = ["popolazione", "strutture", "vodafone", "presenze_alb", "presenze_extralb"]
PROCESSED_OLD = ["popolazione_pr", "strutture_pr", "vodafone_pr", "presenze_alb_pr", "presenze_extralb_pr"]

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

RENAMING_STRUTTURE = {
    "Esercizi alberghieri Numero": "alberghieri strutture",
    "Esercizi alberghieri Letti": "alberghieri posti_letto",
    "Esercizi extralberghieri Numero": "extra alb. Strutture",
    "Esercizi extralberghieri Letti": "extra alb. Posti_letto",
    "Totale Numero": "tot convenzionali strutture",
    "Totale Letti": "tot convenzionali posti_letto",
}

MONTHS_MAPPING = {
    "Gennaio": 1,
    "Febbraio": 2,
    "Marzo": 3,
    "Aprile": 4,
    "Maggio": 5,
    "Giugno": 6,
    "Luglio": 7,
    "Agosto": 8,
    "Settembre": 9,
    "Ottobre": 10,
    "Novembre": 11,
    "Dicembre": 12,
}

# ---------------------------------------------------------------------------
# STANDARDIZATION + PROCESSING OF UPDATE DATA
# ---------------------------------------------------------------------------


## Popolazione
def standardize_and_process_popolazione_2025(df, mapping_comuni):
    """Standardization function for popolazione. It is computed as the arithmetic mean between population at 01/01/2025 and 01/01/2026."""
    df = df.copy()
    df["popolazione"] = (
        (df["Popolazione residente al 1.1.2025"] +
         df["Popolazione residente al 1.1.2026"]) / 2
    ).round().astype(int)
    df = df.rename(columns={"Comuni": "comune"}).sort_values(by="comune")
    df["anno"] = 2025
    # standardization and process
    return process_popolazione(standardize_popolazione_columns(df), mapping_comuni)


## Strutture
def standardize_upd_strutture(df):
    df = df.rename(columns=RENAMING_STRUTTURE).copy()
    for c in df.columns.drop(['comune', 'anno']):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)   # manage "-"

    ## Logic to compute CONV / NON CONV
    df['tot convenzionali strutture'] = df["alberghieri strutture"] + df["extra alb. Strutture"]
    df['tot convenzionali posti_letto'] = df['alberghieri posti_letto'] + df['extra alb. Posti_letto']

    # complessivo as sum of all cathegories
    df['COMPLESSIVO numero'] = df["alberghieri strutture"] + df["extra alb. Strutture"] + df["Alloggi turistici Numero"] + df["Alloggi a disposizione Numero"]
    df['COMPLESSIVO posti_letto'] = df['alberghieri posti_letto'] + df['extra alb. Posti_letto'] + df["Alloggi turistici Letti"] + df["Alloggi a disposizione Letti"]

    ## in old terminology, all privati = all non conv
    df['all. privati numero'] = df['COMPLESSIVO numero'] - df['tot convenzionali strutture']
    df['all. privati posti_letto'] = df['COMPLESSIVO posti_letto'] - df['tot convenzionali posti_letto']

    ## checks
    assert (df['all. privati numero'] >= 0).all(), f"There are {len(df[df['all. privati numero'] < 0])} lines with strutture non conv < 0 "
    assert (df['all. privati posti_letto'] >= 0).all(), f"There are {len(df[df['all. privati posti_letto'] < 0])} lines with beds strutture non conv < 0 "

    return standardize_strutture_columns(df.filter(regex=r'^(?!_)'))


def standardize_and_process_strutture_2024(df, mapping_comuni):
    """Adapt 2024 structures to the current standard structures schema, in order to reuse standardize_strutture_columns() + process_strutture()"""
    df = df.rename(columns={"Comuni": "comune"})
    df["anno"] = 2024
    return process_strutture(standardize_upd_strutture(df), mapping_comuni)


def standardize_and_process_strutture_2025(df, mapping_comuni):
    """Adapts the strutture 2025 to the "standard" one in order to reuse standardize_strutture_columns() + process_strutture()"""
    df = _remove_unnamed(df)
    df = df.rename(columns={"Comune": "comune"})
    df["anno"] = 2025
    return process_strutture(standardize_upd_strutture(df), mapping_comuni)


## Vodafone
def standardize_and_process_vodafone_2025(df, mapping_vodafone, geojson):
    """Adapt the new Vodafone data using the dedicated functions."""
    return process_vodafone(standardize_vodafone_columns(df, geojson), mapping_vodafone)


## Presenze
def process_presenze_ispat_2025(df, apts, anno=2025):
    """Convert the grouped ISPAT monthly dataframe into long format."""
    columns = ["Mese"]
    for ambito in apts[1:]:
        columns.extend([f"{ambito} Italiani", f"{ambito} Stranieri", f"{ambito} Totale"])

    if len(columns) != df.shape[1]:
        raise ValueError(f"Expected {len(columns)} columns, found {df.shape[1]}")

    df = df.copy()
    df.columns = columns

    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Anno"].copy()

    mapped_months = df["Mese"].map(MONTHS_MAPPING)
    if mapped_months.isna().any():
        raise ValueError(
            "Mesi non riconosciuti: "
            f"{df.loc[mapped_months.isna(), 'Mese'].unique()}"
        )

    df["Mese"] = mapped_months.astype(int)
    value_cols = [c for c in df.columns if c.endswith(" Totale")]

    long_df = df.melt(
        id_vars=["Mese"],
        value_vars=value_cols,
        var_name="Ambito",
        value_name="Presenze"
    )
    long_df["Ambito"] = long_df["Ambito"].str.removesuffix(" Totale").str.strip()

    long_df["Presenze"] = pd.to_numeric(long_df["Presenze"], errors="coerce")
    if long_df["Presenze"].isna().any():
        bad = long_df.loc[long_df["Presenze"].isna(), "Ambito"].unique()
        raise ValueError(f"Valori non numerici per ambiti: {bad}")

    long_df["Presenze"] = long_df["Presenze"].astype(int)
    long_df["Anno"] = anno
    return long_df[["Ambito", "Anno", "Mese", "Presenze"]]  # now it's in the right format to be given as input of standardization 

def standardize_and_process_presenze_alb_2025(df, apts, mapping_apt):
    long_df = process_presenze_ispat_2025(df, apts)
    std = standardize_presenze_columns(
        long_df,
        cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"},
    )
    return process_presenze_ISPAT(
        std, mapping_apt, PRESENZE_ALB_VALUE_COLS, provincia=False
    )


def standardize_and_process_presenze_extralb_2025_apt(df, apts, mapping_apt):
    """New: extra-alberghiero data at APT granularity.
    Kept as an update artifact, although the current final
    phenomenon uses the provincial xalb dataset.
    """
    long_df = process_presenze_ispat_2025(df, apts)
    std = standardize_presenze_columns(
        long_df,
        cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"},
    )
    processed = process_presenze_ISPAT(
        std, mapping_apt, PRESENZE_ALB_VALUE_COLS, provincia=False
    )
    return processed.rename(columns={"presenze_alb": "presenze_xalb"})


def standardize_and_process_presenze_extralb_2025_prov(df, mapping_comuni):
    """Standardize the provincial extra-alberghiero dataset."""
    df = _remove_unnamed(df).copy()
    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Totale"].reset_index(drop=True)
    df["Mese"] = df["Mese"].map(MONTHS_MAPPING)
    if df["Mese"].isna().any():
        raise ValueError(
            "Mesi non riconosciuti: "
            f"{df.loc[df['Mese'].isna(), 'Mese'].unique()}"
        )

    alb_col = "Esercizi alberghieri Totale"
    xalb_col = "Esercizi extralberghieri Totale"

    for col in (alb_col, xalb_col):
        if col not in df.columns:
            raise ValueError(f"Colonna attesa non trovata: {col}")

    df_xalb_prov = pd.DataFrame({
        "Anno": 2025,
        "Mese": df["Mese"].astype(int),
        "Presenze alberghi": pd.to_numeric(df[alb_col], errors="coerce"),
        "Presenze extra-alberghi": pd.to_numeric(df[xalb_col], errors="coerce"),
    })

    if df_xalb_prov[["Presenze alberghi", "Presenze extra-alberghi"]].isna().any().any():
        raise ValueError("Not numeric values for 'Presenze' found")

    std = standardize_presenze_columns(
        df_xalb_prov,
        cols_renaming={
            "Presenze alberghi": "presenze_alb",
            "Presenze extra-alberghi": "presenze_xalb",
        },
    )
    return process_presenze_ISPAT(
        std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True
    )

# ---------------------------------------------------------------------------
# DOWNLOAD + STANDARDIZE + PROCESS UPDATE
# ---------------------------------------------------------------------------

def process_updated_data(out_dir=UPDATE_PROCESSED_DIR, type_format="csv", datasets=None):
    """Download, standardize and process only the requested update-source datasets.
    datasets: subset of ALL_DATASETS, default = all."""
    ## download mapping and geojson data 
    datasets = set(datasets) if datasets else set(ALL_DATASETS)
    if datasets - set(ALL_DATASETS):
        raise ValueError(f"Unknown dataset(s): {sorted(datasets - set(ALL_DATASETS))}. Valid: {ALL_DATASETS}")

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
        dict_dfs["strutture_24_pr"] = standardize_and_process_strutture_2024(strutture_24_raw, mapping_comuni)
        dict_dfs["strutture_25_pr"] = standardize_and_process_strutture_2025(strutture_25_raw, mapping_comuni)

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
        4. recompute final phenomena
    datasets: subset of ALL_DATASETS to actually update; default None updates all."""

    logging.info("=== STEP 1: standardize/process update data (%s) ===", datasets if datasets else "all")
    new_dfs = process_updated_data(out_dir=update_dir, type_format=type_format, datasets=datasets)

    logging.info("=== STEP 2: read current processed data ===")
    processed_dfs_old = {name: read_df(processed_dir, name, type_format) for name in PROCESSED_OLD}

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
    selected_datasets = set(datasets) if datasets else set(ALL_DATASETS)
    phenomena_to_save = {}

    if "popolazione" in selected_datasets:
        phenomena_to_save["phen_popolazione"] = all_phenomena["phen_popolazione"]

    if "strutture" in selected_datasets:
        phenomena_to_save["phen_strutture"] = all_phenomena["phen_strutture"]

    if selected_datasets.intersection({"vodafone", "presenze_alb", "presenze_extralb"}):
        phenomena_to_save["phen_presenze"] = all_phenomena["phen_presenze"]

    check_output_dir(final_dir)
    final_dir.mkdir(parents=True, exist_ok=True)

    save_computed_dfs(
        phenomena_to_save,
        local=True,
        type_format=type_format,
        path_saving=final_dir,
    )

    logging.info("=== UPDATE COMPLETED ===")
    return merged_dfs


if __name__ == "__main__":
    update_pipeline(datasets=["vodafone", "presenze_alb", "presenze_extralb", "pippo"])