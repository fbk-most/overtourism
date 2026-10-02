"""
This file contains the functions to align the dataframes of the updated datasets (2024 and 2025) to the standard one.
"""

import pandas as pd 
from data_preparation.utils.common import _remove_unnamed

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


def compute_popolazione_aritmetic_mean(df) -> pd.Series:
    """Computes the popolazione as the aritmetic mean"""
    return ((df["Popolazione residente al 1.1.2025"] +
             df["Popolazione residente al 1.1.2026"]) / 2).round().astype(int)


def align_data_popolazione_2025(df):
    df = df.copy()
    df = df.rename(
        columns={
            "Comuni": "comune", 
            "Popolazione residente al 1.1.2025": "popolazione"
        }).sort_values(by="comune")
    ## assign the 2025 popolazione as 1 jan 
    df["anno"] = 2025
    return df


def align_data_strutture(df, comune_col= "Comune", year=2024):
    df = df.copy()
    df = _remove_unnamed(df)
    df = df.rename(columns={comune_col: "comune", **RENAMING_STRUTTURE}).copy()
    df['anno'] = year
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
    assert (df['all. privati numero'] >= 0).all(), f"There are {len(df[df['all.privati numero'] < 0])} lines with strutture non conv < 0 "
    assert (df['all. privati posti_letto'] >= 0).all(), f"There are {len(df[df['all. privati posti_letto'] < 0])} lines with beds strutture non conv < 0 "
    return df.filter(regex=r'^(?!_)')


def align_presenze_ispat_apts(df, apts, anno=2025):
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


def align_presenze_ispat_prov(df):
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

    df_alb_xalb_prov = pd.DataFrame({
        "Anno": 2025,
        "Mese": df["Mese"].astype(int),
        "Presenze alberghi": pd.to_numeric(df[alb_col], errors="coerce"),
        "Presenze extra-alberghi": pd.to_numeric(df[xalb_col], errors="coerce"),
    })
    
    if df_alb_xalb_prov[["Presenze alberghi", "Presenze extra-alberghi"]].isna().any().any():
        raise ValueError("Not numeric values for 'Presenze' found")

    return df_alb_xalb_prov