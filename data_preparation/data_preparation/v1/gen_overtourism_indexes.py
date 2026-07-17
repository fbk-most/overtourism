import json
import os
import re
from pathlib import Path

import numpy as np
import geopandas as gpd

from data_preparation.utils import put_dataframe, log_dataframe, get_dataframe, get_geojson

PATH_MAPPING = Path(__file__).parent.resolve() / "mapping"

def init_overtourism(geojson):
    try:
        mf = get_geojson(geojson, local=True)
    except Exception:
        print(f"Generate {geojson} first!")
        exit(1)

    df = mf[['comune', 'ID']].copy()
    df['level'] = 0

    return df

with open(PATH_MAPPING / "vodafone_Trento.json", 'r') as f:
    vodafone_map = json.load(f)
# TODO: move the following map in the map file?
vodafone_map['SAN GIOVANNI DI FASSA-SEN JAN'] = [ 22250 ]

def clean_comune(comune):
    patterns = {
        r'^BORGO CHIESE \+ CASTEL CONDINO \+ PIEVE DI BONO-PREZ$': 'BORGO CHIESE + CASTEL CONDINO + PIEVE DI BONO-PREZZO',
        r'^BENESELLO \+ CALLIANO \+ VOLANO$': 'BESENELLO + CALLIANO + VOLANO',
        r'^SANT\'ORSOLA TERME \+ FRASSILONGO \+ PALU\' DEL FERSIN$': 'SANT\'ORSOLA TERME + FRASSILONGO + PALU\' DEL FERSINA',
        r' \(.*\)$': '',
        r'^TN .*$': 'TRENTO',
        r'^POZZA DI FASSA$': 'SAN GIOVANNI DI FASSA-SEN JAN',
        r'^VIGO DI FASSA$': 'SAN GIOVANNI DI FASSA-SEN JAN',
    }
    for p in patterns:
        comune = re.sub(p, patterns[p], comune)
    #comune = comune.replace("'", "")
    return comune

def map_comune_to_id(comune):
    comune = clean_comune(comune)
    assert comune in vodafone_map.keys(), f"Comune {comune} not found!"
    return vodafone_map[comune]

def compute_overtourism_factor(row, df_factor):
    comune = row["comune"]
    if comune in df_factor["comune"].values:
        return df_factor[df_factor["comune"] == comune]["overtourism_level"].values[0]
    comune = clean_comune(comune)
    if comune in df_factor["comune"].values:
        return df_factor[df_factor["comune"] == comune]["overtourism_level"].values[0]
    ids = map_comune_to_id(row["comune"])
    val = None
    for id in ids:
        id = str(id)
        if id in df_factor["ID"].values.astype(str):
            if val is None:
                val = df_factor[df_factor["ID"].astype(str) == id]["overtourism_level"].values[0]
            else:
                val = max(val, df_factor[df_factor["ID"].astype(str) == id]["overtourism_level"].values[0])
        else:
            val = None
            break
    assert val is not None, f"Comune {comune} not found!"
    return val

def add_overtourism_factor(df, df_factor, factor_name):
    df[factor_name + "_val"] = df.apply(
        lambda r: compute_overtourism_factor(r, df_factor),
        axis='columns'
    )
    df["level"] = df["level"] + df[factor_name + "_val"]
    df[factor_name] = df.apply(
        lambda r: "*" * r[factor_name + "_val"] if r[factor_name + "_val"] else "/",
        axis='columns'
    )
    df.drop(columns=[factor_name + "_val"], inplace=True)

def emit_overtourism(df):
    df['anno'] = 2024
    df.set_index(['comune', 'anno'], inplace=True)
    return df

def compute_top(df, key, anno=None):
    df = df.reset_index()
    if anno is not None:
        df = df[df['anno'] == anno]
    df = df[["ID", "comune", key]]
    df["overtourism_level"] = 0
    q1_size = round(df.shape[0] / 4)
    q1 = df.nlargest(q1_size, key, keep="all")
    df.loc[q1.index, "overtourism_level"] = 1
    o1_size = round(df.shape[0] / 8)
    o1 = df.nlargest(o1_size, key, keep="all")
    df.loc[o1.index, "overtourism_level"] = 2
    s1_size = round(df.shape[0] / 16)
    s1 = df.nlargest(s1_size, key, keep="all")
    df.loc[s1.index, "overtourism_level"] = 3
    return df[["ID","comune","overtourism_level"]]

def compute_max(df, key, anno=None):
    df = df.reset_index()
    if anno is not None:
        df = df[df['anno'] == anno]
    df = df[["ID", "comune", key]]
    df["overtourism_level"] = 0
    max = df.nlargest(1, key, keep="all")
    df.loc[max.index, "overtourism_level"] = 2
    return df[["ID","comune","overtourism_level"]]


def compute_overtourism_df():
    local = True

    ricettivita_top = compute_top(get_dataframe("df_tasso_ricettivita", local=local), key="ricettivita", anno=2023)
    turisticita_estate_top = compute_top(get_dataframe("df_tasso_turisticita_estate", local=local), key="turisticita", anno=2023)
    stagionalita_top = compute_top(get_dataframe("df_stagionalita_presenze", local=local), key="stagionalita", anno=2023)
    flusso_estate_top = compute_max(get_dataframe("df_flussi_estate", local=local), key="level_in_escursionisti_sempre", anno=2024)

    # TODO: Manage differently!
    turisticita_estate_top.loc[turisticita_estate_top["comune"] == 'SAN GIOVANNI DI FASSA', "comune"] = 'SAN GIOVANNI DI FASSA-SEN JAN'
    stagionalita_top.loc[stagionalita_top["comune"] == 'SAN GIOVANNI DI FASSA', "comune"] = 'SAN GIOVANNI DI FASSA-SEN JAN'

    df_overtourism = init_overtourism("map_vodafone_2024")

    add_overtourism_factor(df_overtourism, ricettivita_top, "ricettivita")
    add_overtourism_factor(df_overtourism, turisticita_estate_top, "turisticita")
    add_overtourism_factor(df_overtourism, stagionalita_top, "stagionalita")
    add_overtourism_factor(df_overtourism, flusso_estate_top, "flusso")

    return emit_overtourism(df_overtourism)


def local():
    DF_OVERTURISMO = compute_overtourism_df() 
    put_dataframe(DF_OVERTURISMO, "df_overturismo", type='parquet')

def main():
    DF_OVERTURISMO = compute_overtourism_df() 
    log_dataframe(DF_OVERTURISMO.reset_index(), "df_overturismo")


if __name__ == "__main__": 
    local()