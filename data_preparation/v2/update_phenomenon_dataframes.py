"""
File dedicated to update the phenomena 
The updating procedure shall include a STANDARDIZATION PART (to make the new phenomena compatible with the old ones) and an UPDATE PART (taking into account data overlaps, which are for choice updated to the newest ones)
"""

import logging
from data_preparation.v2.utils.utils import (
    get_mapping,
    get_s3,
    save_computed_dfs
)
from data_preparation.v2.standardize_raw_data import (
    standardize_presenze_ISPAT_extralb,
    standardize_popolazione, 
    standardize_strutture,
    standardize_vodafone,
    standardize_presenze_ISPAT_alb,
    _pre_filtering_vodafone_attendences,
    standardize_base_raw_data,
    standard_ordering_cols
)
from pathlib import Path 
import pandas as pd 
import geopandas as geopd 

logging.basicConfig(level=logging.INFO)
SAVEPATH_STD_DATA_UPD = Path(__file__).parent / "data_std" / "updated"
SAVEPATH_STD_DATA_MERGED = Path(__file__).parent / "data_std" / "merged_std"

BASE_COLS = ["DATA", "LOCATION", "ID_COMUNE"]
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

def _remove_unnamed(df):
    """Removes unnamed from header.

    If the columns are already flat strings (as in the reconstructed TSVs), this is a no-op and we leave them untouched.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df.copy()

    top = pd.Series([c[0] for c in df.columns])
    top = top.where(~top.astype(str).str.startswith("Unnamed"), pd.NA).ffill()
    bottom = pd.Series([c[1] for c in df.columns])

    df = df.copy()
    df.columns = [
        str(t).strip() if str(b).startswith("Unnamed") or pd.isna(b)
        else f"{str(t).strip()} {str(b).strip()}"
        for t, b in zip(top, bottom)
    ]
    return df

def _read_grouped_presenze_tsv(data_source, sep: str = "\t") -> pd.DataFrame:
    """
    This function reshapes the grouped header into flat columns, like: Mese, Esercizi alberghieri Italiani, Esercizi alberghieri Stranieri, ...
    """
    if hasattr(data_source, "read"):
        data = data_source.getvalue().decode("utf-8")
        lines = [ln.rstrip("\n") for ln in data.splitlines() if ln.strip()]
        path_desc = "buffer"
    else:
        path = str(data_source)
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        path_desc = path

    if len(lines) < 2:
        raise ValueError(f"File troppo corto per header a 2 righe: {path_desc}")

    first = [c.strip() for c in lines[0].split(sep)]
    second = [c.strip() for c in lines[1].split(sep)]

    groups = [c for c in first if c and c.lower() != "mese"]
    if not groups:
        raise ValueError(f"Header della prima riga non riconosciuto: {first}")

    names = ["Mese"]
    for group in groups:
        names.extend([f"{group} Italiani", f"{group} Stranieri", f"{group} Totale"])

    if len(names) != len(second) + 1:
        # Fallback: if the file is already sufficiently aligned, read it with a
        # MultiIndex-like structure instead of manually reconstructing names.
        if hasattr(data_source, "read"):
            return pd.read_csv(data_source, sep=sep, header=[0, 1], dtype=str)
        return pd.read_csv(path_desc, sep=sep, header=[0, 1], dtype=str)

    if hasattr(data_source, "read"):
        return pd.read_csv(
            pd.io.common.StringIO(data),
            sep=sep,
            header=None,
            names=names,
            skiprows=2,
            dtype=str,
        )

    return pd.read_csv(
        path_desc,
        sep=sep,
        header=None,
        names=names,
        skiprows=2,
        dtype=str,
    )

## popolazione 
def standardize_upd_popolazione_2025(df, mapping_comuni):
    """Standardization function for popolazione"""
    # popolazione del 2025 calcolata come media aritmetica 
    df['popolazione'] = ((df['Popolazione residente al 1.1.2025'] + df['Popolazione residente al 1.1.2026']) / 2).round().astype(int)    # dataframe containing data 1 gen 2025 + 1 gen 2026
    df = df.sort_values(by = "Comuni") 
    df['anno'] = 2025
    return standardize_popolazione(df, mapping_comuni, comune_col = "Comuni", date_col= "anno")

## strutture annuario 
def standardize_upd_strutture_2024(df, mapping_comuni):
    """Adapts the strutture 2024 to the "standard" one in order to reuse standardize_strutture()"""
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"] = 2024
    return standardize_strutture(df[["Comuni", "anno"] + list(RENAMING_STRUTTURE.values())], mapping_comuni, comune_col = "Comuni")

def standardize_upd_strutture_2025(df, mapping_comuni):
    """Adapts the strutture 2025 to the "standard" one in order to reuse standardize_strutture()"""
    df = _remove_unnamed(df)
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"]=2025
    return standardize_strutture(df[["Comune", "anno"] + list(RENAMING_STRUTTURE.values())], mapping_comuni, comune_col = "Comune")

## presenze ispat (ALB/EXTRALB)
def _process_presenze_ispat_2025(df, apts, mapping, anno=2025):
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
    long_df = _process_presenze_ispat_2025(df, apts, mapping, anno)
    return standardize_presenze_ISPAT_alb(long_df, mapping)

def standardize_upd_presenze_extralb_apt_2025(df, apts, mapping, anno=2025):
    long_df = _process_presenze_ispat_2025(df, apts, mapping, anno)
    std_df = standardize_presenze_ISPAT_alb(long_df, mapping) # standardizes with alb procedure because it's at atp granularity 
    return std_df.rename(columns={"presenze_alb": "presenze_xalb"}) 

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

    return standardize_presenze_ISPAT_extralb(
        pd.DataFrame({
            "Anno": anno,
            "Mese": df["Mese"].astype(int),
            "Presenze alberghi": presenze_alb.astype(int),
            "Presenze extra-alberghi": presenze_xalb.astype(int),
        }), mapping_comuni)

def standardize_upd_data(local = True, type_format = "csv"):
    """Standardization function for the new data """
    ## download mapping and geojson data 
    logging.info("Downloading and standardizing mappings...") 
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_apt= get_mapping("map_comuni_into_apt.json")
    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))
    
    logging.info("Downloading dataframe 'popolazione_2026_ISPAT.csv'...")
    popolazione_df = pd.read_csv(get_s3("popolazione_2026_ISPAT.csv")) 
    logging.info("Downloading dataframe 'vodafone_attendences_new.csv'...")
    vodafone_df = pd.read_csv(get_s3("vodafone_attendences_new.csv"))
    ## TODO: upload the version xlsx for consistency
    logging.info("Downloading strutture_annuario_2024.ods from S3...")
    strutture_24_df = pd.read_excel(get_s3("strutture_annuario_2024.ods"),engine='odf')

    logging.info("Downloading strutture_annuario_2025.xlsx'...")
    strutture_25_df = pd.read_excel(get_s3("numero_strutture_ISPAT_2025.xlsx"), header=[0, 1])

    logging.info("Downloading presenze_alb_2025.csv from S3...")
    raw_alb = pd.read_csv(get_s3("presenze_alb_2025.csv"), sep="\t", header=None, skiprows=2, dtype=str)
    apts = [x.strip() for x in get_s3("presenze_alb_2025.csv").getvalue().decode("utf-8").splitlines()[0].split("\t")]

    logging.info("Downloading presenze_xalb_2025.csv from S3...")
    presenze_extralb_apt_df = pd.read_csv(get_s3("presenze_xalb_2025.csv"), sep="\t", header=None, skiprows=2, dtype=str)
    apts_extralb = [x.strip() for x in get_s3("presenze_xalb_2025.csv").getvalue().decode("utf-8").splitlines()[0].split("\t")]

    logging.info("Downloading presenze_xalb_2025_prov.csv from S3...")
    raw_extralb_provincia = _read_grouped_presenze_tsv(get_s3("presenze_xalb_2025_prov.csv"))

    logging.info("Standardization of data...")
    popolazione_df = standardize_upd_popolazione_2025(popolazione_df, mapping_comuni)
    strutture_24_df = standardize_upd_strutture_2024(strutture_24_df, mapping_comuni)   
    strutture_25_df = standardize_upd_strutture_2025(strutture_25_df, mapping_comuni)

    vodafone_df = _pre_filtering_vodafone_attendences(vodafone_df)
    vodafone_df = standardize_vodafone(vodafone_df, mapping_vodafone, geojson_comuni_json_data)

    presenze_ispat = standardize_upd_presenze_alb_2025(raw_alb, apts, mapping_apt) 
    presenze_extralb_apt_df = standardize_upd_presenze_extralb_apt_2025(presenze_extralb_apt_df, apts_extralb, mapping_apt) 

    presenze_extralb_provincia_df = standardize_upd_presenze_extralb_2025(raw_extralb_provincia, mapping_comuni)
    dict_dfs = {
        "popolazione_25_std" : popolazione_df,
        "strutture_24_std" : strutture_24_df,
        "strutture_25_std" : strutture_25_df,
        "vodafone_25_std" : vodafone_df,
        "presenze_alb_25_std" : presenze_ispat,
        "presenze_extralb_25_apt_std" : presenze_extralb_apt_df,
        "presenze_extralb_25_prov_std" : presenze_extralb_provincia_df
    }
    save_path = Path(SAVEPATH_STD_DATA_UPD).resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    save_computed_dfs(dict_dfs=dict_dfs, local = local, type_format = type_format, path_saving=save_path)
    return dict_dfs


## UPDATE OF PHENOMENA
## functions to define updates: save merged dataframes 
def _make_hashable(value):
    """Converte un valore potenzialmente non-hashable (lista) in una forma
    hashable stabile, per poterlo usare come chiave di drop_duplicates.
    Liste -> tuple (ordinate, per stabilità indipendentemente dall'ordine
    con cui i comuni sono stati raccolti a monte)."""
    if isinstance(value, list):
        return tuple(sorted(value))
    return value


def merge_update(df_old: pd.DataFrame, df_new: pd.DataFrame, common_cols=None) -> pd.DataFrame:
    """Merges old and new: checks the columns and updates the data if there is some intersection.
    If common_cols is set to None, df_old.columns are used as reference"""
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
        .drop(columns="_dedup_key")
    )
    # print(merged["ID_COMUNE"].apply(type).value_counts())
    return standard_ordering_cols(merged.sort_values(by=['DATA', 'LOCATION']).reset_index(drop=True))


def merge_dataframes(old_dfs: dict, new_dfs: dict) -> dict:
    """Merge vecchio/nuovo per ciascun fenomeno. strutture_std riceve due
    aggiornamenti in sequenza (2024 poi 2025)."""
    pop_old, pop_new = old_dfs['popolazione_std'], new_dfs['popolazione_25_std']
    strutture_old, strutture_new_24, strutture_new_25 =  old_dfs['strutture_std'], new_dfs['strutture_24_std'], new_dfs['strutture_25_std']
    vodafone_old, vodafone_new = old_dfs['vodafone_std'], new_dfs['vodafone_25_std']
    presenze_alb_old, presenze_alb_new = old_dfs['presenze_alb_std'], new_dfs['presenze_alb_25_std']
    presenze_xalb_old, presenze_xalb_new = old_dfs['presenze_extralb_std'], new_dfs['presenze_extralb_25_prov_std']
    
    popolazione = merge_update(pop_old, pop_new, common_cols = ['popolazione'])

    strutture = merge_update(strutture_old, strutture_new_24)  # in this case, they have the same structure, so default common cols is used
    strutture = merge_update(strutture, strutture_new_25)
    vodafone = merge_update(vodafone_old, vodafone_new)

    presenze_alb = merge_update(presenze_alb_old, presenze_alb_new)
    presenze_extralb = merge_update(presenze_xalb_old,presenze_xalb_new)

    return {
        "popolazione_std": popolazione,
        "strutture_std": strutture,
        "vodafone_std": vodafone,
        "presenze_alb_std": presenze_alb,
        "presenze_extralb_std": presenze_extralb,
        "presenze_extralb_apt_std": new_dfs["presenze_extralb_25_apt_std"],  # new granularity
    }


if __name__=="__main__":
    old_dfs = standardize_base_raw_data(local=True, type_format="parquet")
    new_dfs = standardize_upd_data(local=True, type_format="parquet")
    merged_dfs = merge_dataframes(old_dfs, new_dfs)

    save_path = Path(SAVEPATH_STD_DATA_MERGED).resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    save_computed_dfs(
        dict_dfs=merged_dfs,
        local=True,
        type_format="parquet",
        path_saving=save_path,
    )
    print("Process finished.")