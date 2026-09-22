"""
File dedicated to update the phenomena 
The updating procedure shall include a STANDARDIZATION PART (to make the new phenomena compatible with the old ones) and an UPDATE PART (taking into account data overlaps, which are for choice updated to the newest ones)
"""

import logging
from data_preparation.v2.utils.utils import (
    get_mapping,
    get_s3,
)
from data_preparation.v2.standardize_raw_data import (
    standardize_mapping, 
    standardize_popolazione, 
    standardize_strutture,
    standardize_vodafone,
    standardize_presenze_ISPAT_alb,
    standardize_presenze_ISPAT_extralb,
    _pre_filtering_vodafone_attendences
)
import pandas as pd 
import geopandas as geopd 

logging.basicConfig(level=logging.INFO)

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
    df['popolazione'] = ((df['Popolazione residente al 1.1.2025'] + df['Popolazione residente al 1.1.2026']) / 2).round().astype(int)    # dataframe containing daata 1 gen 2025 + 1 gen 2026
    df = df.sort_values(by = "Comuni") 
    df['anno'] = 2025
    return standardize_popolazione(df, mapping_comuni, comune_col = "Comuni", date_col= "anno")

## strutture annuario 

def standardize_upd_strutture_2024(mapping_comuni):
    """Adapts the strutture to the "standard" one in order to reuse standardize_strutture()"""
    ## TODO: upload the version xlsx for consistency
    logging.info("Downloading strutture_annuario_2024.csv from S3...")
    df = pd.read_excel(
        get_s3("strutture_annuario_2024.ods"),
        engine='odf'
    )
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"] = 2024
    return standardize_strutture(df[["Comuni", "anno"] + list(RENAMING_STRUTTURE.values())], mapping_comuni, comune_col = "Comuni")

def _remove_unnamed(df):
    """Removes unnamed from header"""
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
def standardize_upd_strutture_2025(mapping_comuni):
    """Adapts the strutture to the "standard" one in order to reuse standardize_strutture()"""
    df = pd.read_excel(get_s3("numero_strutture_ISPAT_2025.xlsx"), header=[0, 1])

    df = _remove_unnamed(df)
    df = df.rename(columns=RENAMING_STRUTTURE)
    df["anno"]=2025
    return standardize_strutture(df[["Comune", "anno"] + list(RENAMING_STRUTTURE.values())], mapping_comuni, comune_col = "Comune")

## vodafone attendences 

def standardize_upd_data():
    """Standardization function for the new data """
    logging.info("Downloading dataframe 'popolazione_2026_ISPAT'...")
    df = pd.read_csv(get_s3("popolazione_2026_ISPAT.csv")) 
    mapping_comuni = standardize_mapping(get_mapping("mapping_comuni_ISTAT.json"))
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))

    popolazione_df = standardize_upd_popolazione_2025(df, mapping_comuni)
    print(popolazione_df.head())

    logging.info("Downloading strutture_annuario_2024.csv'...")
    strutture_24_df = standardize_upd_strutture_2024(mapping_comuni)
    print(strutture_24_df.head())
    strutture_25_df = standardize_upd_strutture_2025(mapping_comuni)
    print(strutture_25_df.head())

    vodafone_df = pd.read_csv(get_s3("vodafone_attendences_new.csv"))
    logging.info("Downloading dataframe 'vodafone_attendences_new.csv'...")
    vodafone_df = _pre_filtering_vodafone_attendences(vodafone_df)
    vodafone_df = standardize_vodafone(df, mapping_vodafone, geojson_comuni_json_data)

## UPDATE OF PHENOMENA
## functions to define updates: save merged dataframes 

if __name__=="__main__":
    standardize_upd_data()
