"""
File dedicated to update the phenomena 
The updating procedure shall include a STANDARDIZATION PART (to make the new phenomena compatible with the old ones) and an UPDATE PART (taking into account data overlaps, which are for choice updated to the newest ones)
"""

import logging
from data_preparation.v2.utils.utils import (
    get_mapping,
    get_s3,
    save_computed_dfs,
    _read_grouped_presenze_tsv,
    _remove_unnamed
)
from data_preparation.v2.standardize_raw_data import (
    standardize_popolazione_columns,
    standardize_strutture_columns,
    standardize_vodafone_columns,
    stadardize_presenze_columns,
    standard_ordering_cols,
    process_popolazione,
    process_strutture,
    process_vodafone,
    process_presenze_ISPAT,
    main_preprocessing_raw_data,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_XALB_VALUE_COLS,
)

from pathlib import Path 
import pandas as pd 
import geopandas as geopd 

logging.basicConfig(level=logging.INFO)
SAVEPATH_STD_DATA_UPD = Path(__file__).parent / "data_std" / "updated"
SAVEPATH_STD_DATA_MERGED = Path(__file__).parent / "data_std" / "merged_std"

BASE_COLS = ["DATA", "ID_COMUNE"]  # LOCATION removed: process_*() removes it
## STANDARDIZATION OF NEW DATA 
RENAMING_STRUTTURE = {
    "Esercizi alberghieri Numero": "alberghieri strutture",
    "Esercizi alberghieri Letti": "alberghieri posti_letto",
    "Esercizi extralberghieri Numero": "extra alb. Strutture",
    "Esercizi extralberghieri Letti": "extra alb. Posti_letto",
    "Totale Numero": "tot convenzionali strutture",
    "Totale Letti": "tot convenzionali posti_letto",
    "Alloggi turistici Numero": "all. privati numero",
    "Alloggi turistici Letti": "all. privati posti_letto",
    "Alloggi a disposizione Numero": "all.disposizione numero",
    "Alloggi a disposizione Letti": "all. disposizione posti_letto",
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

## popolazione 
def standardize_upd_popolazione_2025(df, mapping_comuni):
    """Standardization function for popolazione"""
    # popolazione del 2025 calcolata come media aritmetica 
    df['popolazione'] = ((df['Popolazione residente al 1.1.2025'] + df['Popolazione residente al 1.1.2026']) / 2).round().astype(int)    # dataframe containing data 1 gen 2025 + 1 gen 2026
    df = df.rename(columns={"Comuni": "comune"}).sort_values(by="comune")
    df['anno'] = 2025
    std = standardize_popolazione_columns(df)
    return process_popolazione(std, mapping_comuni)


## strutture annuario     

def standardize_upd_strutture_2024(df, mapping_comuni):
    """Adapts the strutture 2024 to the "standard" one in order to reuse standardize_strutture_columns() + process_strutture()"""
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"] = 2024
    df = df.rename(columns={"Comuni": "comune"})
    std = standardize_strutture_columns(df[["comune", "anno"] + list(RENAMING_STRUTTURE.values())])
    return process_strutture(std, mapping_comuni)


def standardize_upd_strutture_2025(df, mapping_comuni):
    """Adapts the strutture 2025 to the "standard" one in order to reuse standardize_strutture_columns() + process_strutture()"""
    df = _remove_unnamed(df)
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"]=2025
    df = df.rename(columns={"Comune": "comune"})
    std = standardize_strutture_columns(df[["comune", "anno"] + list(RENAMING_STRUTTURE.values())])
    return process_strutture(std, mapping_comuni)


## vodafone
def standardize_upd_vodafone_2025(df, mapping_vodafone, geojson_comuni_json_data):
    """standardize_vodafone_columns() gestisce già internamente il filtro TOURIST/comune
    (tramite process_vodafone -> _filtering_vodafone_attendences), non serve più
    pre-filtrare a parte come faceva _pre_filtering_vodafone_attendences."""
    std = standardize_vodafone_columns(df, geojson_comuni_json_data)
    return process_vodafone(std, mapping_vodafone)


## presenze ispat (ALB/EXTRALB)
def _process_presenze_ispat_2025(df, apts, anno=2025):
    """Logica comune per estrarre e pulire i dati delle presenze ISPAT 2025"""
    columns = [("Mese", "")]
    for ambito in apts[1:]:
        columns.extend([(ambito, "Italiani"), (ambito, "Stranieri"), (ambito, "Totale")])

    if len(columns) != df.shape[1]:
        raise ValueError(f"Numero colonne non combacia: attese {len(columns)}, trovate {df.shape[1]}")

    df.columns = pd.MultiIndex.from_tuples(columns)
    df.columns = [f"{ambito} {tipo}".strip() if tipo else ambito for ambito, tipo in df.columns]

    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Anno"].reset_index(drop=True)
    mese_mapped = df["Mese"].map(MONTHS_MAPPING)
    if mese_mapped.isna().any():
        raise ValueError(f"Mesi non riconosciuti: {df.loc[mese_mapped.isna(), 'Mese'].unique()}")
    df["Mese"] = mese_mapped.astype(int)

    value_cols = [c for c in df.columns if c.endswith(" Totale")]
    long_df = df.melt(id_vars=["Mese"], value_vars=value_cols, var_name="Ambito", value_name="Presenze")
    long_df["Ambito"] = long_df["Ambito"].str.replace(" Totale$", "", regex=True).str.strip()
    
    long_df["Presenze"] = pd.to_numeric(long_df["Presenze"], errors="coerce")
    if long_df["Presenze"].isna().any():
        bad = long_df.loc[long_df["Presenze"].isna(), "Ambito"].unique()
        raise ValueError(f"Valori non numerici per ambiti: {bad}")
        
    long_df["Presenze"] = long_df["Presenze"].astype(int)
    long_df["Anno"] = anno
    return long_df[["Ambito", "Anno", "Mese", "Presenze"]]  # now it's in the right format to be given as input of standardization 

def standardize_upd_presenze_alb_2025(df, apts, mapping, anno=2025):
    long_df = _process_presenze_ispat_2025(df, apts, anno)
    std = stadardize_presenze_columns(long_df, cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"})
    return process_presenze_ISPAT(std, mapping, PRESENZE_ALB_VALUE_COLS, provincia=False)

def standardize_upd_presenze_extralb_apt_2025(df, apts, mapping, anno=2025):
    long_df = _process_presenze_ispat_2025(df, apts, anno)
    std = stadardize_presenze_columns(long_df, cols_renaming={"Ambito": "comune", "Presenze": "presenze_alb"})
    processed = process_presenze_ISPAT(std, mapping, PRESENZE_ALB_VALUE_COLS, provincia=False)
    return processed.rename(columns={"presenze_alb": "presenze_xalb"})

def standardize_upd_presenze_extralb_2025(df, mapping_comuni, anno=2025):
    """
    Standardization in provincia format.
    """
    df = _remove_unnamed(df)
    df["Mese"] = df["Mese"].astype(str).str.strip()
    df = df[df["Mese"] != "Totale"].reset_index(drop=True)  # rm Totale
    df["Mese"] = df["Mese"].map(MONTHS_MAPPING)
    if df["Mese"].isna().any():
        raise ValueError(f"Mesi non riconosciuti: {df.loc[df["Mese"].isna(), 'Mese'].unique()}")

    for col in ("Esercizi alberghieri Totale", "Esercizi extralberghieri Totale"):
        if col not in df.columns:
            raise ValueError(f"Colonna attesa non trovata: '{col}'. Colonne: {list(df.columns)}")

    presenze_alb = pd.to_numeric(df["Esercizi alberghieri Totale"], errors="coerce")
    presenze_xalb = pd.to_numeric(df["Esercizi extralberghieri Totale"], errors="coerce")
    if presenze_alb.isna().any() or presenze_xalb.isna().any():
        raise ValueError("Valori 'Presenze' non numerici trovati")
 
    df_xalb_prov = pd.DataFrame({
        "Anno": anno,
        "Mese": df["Mese"].astype(int),
        "Presenze alberghi": presenze_alb.astype(int),
        "Presenze extra-alberghi": presenze_xalb.astype(int),
    })
    std = stadardize_presenze_columns(
        df_xalb_prov, cols_renaming={"Presenze alberghi": "presenze_alb", "Presenze extra-alberghi": "presenze_xalb"}
    )
    return process_presenze_ISPAT(std, mapping_comuni, PRESENZE_XALB_VALUE_COLS, provincia=True)
def standardize_upd_data(local = True, type_format = "csv"):
    """Standardization function for the new data """
    ## download mapping and geojson data 
    logging.info("Downloading and standardizing mappings...") 
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_apt= get_mapping("map_comuni_into_apt.json")
    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))

    logging.info("Downloading dataframe 'popolazione_2026_ISPAT.csv'...")
    popolazione_df = pd.read_csv(get_s3("popolazione_2026_ISPAT.csv"))  #  download from ISPAT
    logging.info("Downloading dataframe 'vodafone_attendences_new.csv'...")
    vodafone_df = pd.read_csv(get_s3("vodafone_attendences_new.csv"))
    ## TODO: upload the version xlsx for consistency
    logging.info("Downloading strutture_annuario_2024.ods from S3...")
    strutture_24_df = pd.read_excel(get_s3("strutture_annuario_2024.ods"),engine='odf')  # download from ISPAT 

    logging.info("Downloading strutture_annuario_2025.xlsx'...")
    strutture_25_df = pd.read_excel(get_s3("numero_strutture_ISPAT_2025.xlsx"), header=[0, 1])

    logging.info("Downloading presenze_alb_2025.csv from S3...")
    raw_alb = pd.read_csv(get_s3("presenze_alb_2025.csv"), sep="\t", header=None, skiprows=2, dtype=str)   # download from ISPAT 
    apts = [x.strip() for x in get_s3("presenze_alb_2025.csv").getvalue().decode("utf-8").splitlines()[0].split("\t")]

    logging.info("Downloading presenze_xalb_2025.csv from S3...")
    presenze_extralb_apt_df = pd.read_csv(get_s3("presenze_xalb_2025.csv"), sep="\t", header=None, skiprows=2, dtype=str)   # download from ISPAT 
    apts_extralb = [x.strip() for x in get_s3("presenze_xalb_2025.csv").getvalue().decode("utf-8").splitlines()[0].split("\t")]

    logging.info("Downloading presenze_xalb_2025_prov.csv from S3...")
    raw_extralb_provincia = _read_grouped_presenze_tsv(get_s3("presenze_xalb_2025_prov.csv"))   # download from ISPAT 

    logging.info("Standardization of data...")
    popolazione_df = standardize_upd_popolazione_2025(popolazione_df, mapping_comuni)
    strutture_24_df = standardize_upd_strutture_2024(strutture_24_df, mapping_comuni)   
    strutture_25_df = standardize_upd_strutture_2025(strutture_25_df, mapping_comuni)
    vodafone_df = standardize_upd_vodafone_2025(vodafone_df, mapping_vodafone, geojson_comuni_json_data)
    presenze_ispat = standardize_upd_presenze_alb_2025(raw_alb, apts, mapping_apt)
    presenze_extralb_apt_df = standardize_upd_presenze_extralb_apt_2025(presenze_extralb_apt_df, apts_extralb, mapping_apt)
    presenze_extralb_provincia_df = standardize_upd_presenze_extralb_2025(raw_extralb_provincia, mapping_comuni)
    # Now dictionary at a "processed" level of pipeline
    dict_dfs = {
        "popolazione_25_pr": popolazione_df,
        "strutture_24_pr": strutture_24_df,
        "strutture_25_pr": strutture_25_df,
        "vodafone_25_pr": vodafone_df,
        "presenze_alb_25_pr": presenze_ispat,
        "presenze_extralb_25_apt_pr": presenze_extralb_apt_df,
        "presenze_extralb_25_prov_pr": presenze_extralb_provincia_df,
    }
    save_path = Path(SAVEPATH_STD_DATA_UPD).resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    save_computed_dfs(dict_dfs=dict_dfs, local = local, type_format = type_format, path_saving=save_path)
    return dict_dfs


## UPDATE OF PHENOMENA
## functions to define updates: save merged dataframes 
def _make_hashable(value):
    """Converts a non-hashable (list) item inot an hashable one, in order to use it in drop_duplicates.
    Lists -> tuples (ordered)"""
    if isinstance(value, list):
        return tuple(sorted(value))
    return value


def merge_update(df_old: pd.DataFrame, df_new: pd.DataFrame, common_cols=None) -> pd.DataFrame:
    """Merges old and new: checks the columns and updates the data if there is some intersection.
    If common_cols is set to None, df_old.columns are used as reference
    Merge using DATA + ID_COMUNE (via _make_hashable, to deal with ID_COMUNE lists)"""
    if common_cols is None:
        common_cols = list(df_old.columns)

    all_cols = set(BASE_COLS) | set(common_cols)
    ## si presume questi assert passino dopo la standardizzazione
    assert all_cols.issubset(df_old.columns), f"Columns {all_cols - set(df_old.columns)} not found in old DF"
    assert all_cols.issubset(df_new.columns), f"Columns {all_cols - set(df_new.columns)} not found in new DF"

    merged = pd.concat([df_old[list(all_cols)], df_new[list(all_cols)]], ignore_index=True)
    dedup_key = merged["ID_COMUNE"].apply(_make_hashable)  # we use tuple to avoid type problems 


    merged = (
        merged.assign(_dedup_key=dedup_key)
        .drop_duplicates(subset=["DATA", "_dedup_key"], keep="last")
        .sort_values(by=["DATA", "_dedup_key"])
        .drop(columns="_dedup_key")
        .reset_index(drop=True)
    )    # print(merged["ID_COMUNE"].apply(type).value_counts())

    return standard_ordering_cols(merged)

def merge_dataframes(old_dfs: dict, new_dfs: dict) -> dict:
    """Merges old and new: strutture_pr receives 2024 and then 2025."""
    pop_old, pop_new = old_dfs['popolazione_pr'], new_dfs['popolazione_25_pr']
    strutture_old, strutture_new_24, strutture_new_25 =  old_dfs['strutture_pr'], new_dfs['strutture_24_pr'], new_dfs['strutture_25_pr']
    vodafone_old, vodafone_new = old_dfs['vodafone_pr'], new_dfs['vodafone_25_pr']
    presenze_alb_old, presenze_alb_new = old_dfs['presenze_alb_pr'], new_dfs['presenze_alb_25_pr']
    presenze_xalb_old, presenze_xalb_new = old_dfs['presenze_extralb_pr'], new_dfs['presenze_extralb_25_prov_pr']

    popolazione = merge_update(pop_old, pop_new, common_cols = ['popolazione'])

    strutture = merge_update(strutture_old, strutture_new_24)  # in this case, they have the same structure, so default common cols is used
    strutture = merge_update(strutture, strutture_new_25)
    vodafone = merge_update(vodafone_old, vodafone_new)

    presenze_alb = merge_update(presenze_alb_old, presenze_alb_new)
    presenze_extralb = merge_update(presenze_xalb_old,presenze_xalb_new)

    return {
        "popolazione_pr": popolazione,
        "strutture_pr": strutture,
        "vodafone_pr": vodafone,
        "presenze_alb_pr": presenze_alb,
        "presenze_df_extralb": presenze_extralb,
        "presenze_extralb_apt_pr": new_dfs["presenze_extralb_25_apt_pr"],  # new granularity
    }

def save_merged(merged_dfs,type_format = "csv"):
    save_path = Path(SAVEPATH_STD_DATA_MERGED).resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    save_computed_dfs(
        dict_dfs=merged_dfs,
        local=True,
        type_format=type_format,
        path_saving=save_path,
    )

if __name__=="__main__":
    ## ENTIRE PIPELINE:
    old_dfs = main_preprocessing_raw_data(local=True, type_format="csv")
    new_dfs = standardize_upd_data(local=True, type_format="csv")
    merged_dfs = merge_dataframes(old_dfs, new_dfs)
    save_merged(merged_dfs)
    print("Process finished.")