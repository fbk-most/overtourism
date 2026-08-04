# SPDX-License-Identifier: Apache-2.0
"""
Loads and prepares the base "phenomenon" dataframes used to compute the
capacity / tourism indexes for Trentino, saves them in a format compatible with the Indicators/Phenomenon modules.

Each phenomenon dataframe is typically contains:
  - DATA: the time dimension, at whatever granularity is natural for that
    phenomenon (YYYY for yearly data, YYYY-MM-DD for daily data)
  - LOCATION: the comune/ambito name
  - COMUNE_ID: mapped location identifier(s), when available
  - ... plus the phenomenon's own value column(s)

NOTE ON ID_COMUNE FORMATTING: ISTAT comune codes are conventionally
represented as 6-digit zero-padded strings (e.g. 22001 -> "022001"). The
raw sources / mapping JSONs here store them as plain ints, so every
dataframe that carries an ID_COMUNE column is normalized to the
zero-padded string form right before it's returned, via `pad_id_comune()`.
"""

import json
import logging
from pathlib import Path

import pandas as pd
import geopandas as geopd
from unidecode import unidecode
from utils import get_dataframe, get_s3, log_dataframe, put_dataframe

# from data_preparation.utils import get_dataframe, put_dataframe, log_dataframe, get_s3

logging.basicConfig(level=logging.INFO)

PATH_OVERTOURISM = Path(__file__).parent.parent.parent.parent.resolve() 
PATH_RAW_DATA = Path(__file__).parent.resolve() / "raw_data_trentino"
PATH_MAPPING = Path(__file__).parent.resolve() / ".." / "mapping"
PATH_AIXPA_INDEX_DFS = PATH_OVERTOURISM / 'overtourism' / 'overtourism' / 'database' / 'index_data_v2'
PATH_AIXPA_INDEX_DFS.mkdir(parents=True, exist_ok=True)

assert PATH_MAPPING.exists(), f"Path to mapping does not exist {PATH_MAPPING}"
assert PATH_RAW_DATA.exists(), f"Path to raw data does not exist {PATH_RAW_DATA}"

def customize_unidecode(x):
    """
    Convert the input string, removing accents, converting to uppercase, and stripping whitespace.
    """
    if x.endswith("'"):  # removes also trailing apostrophe if present
        x = x.removesuffix("'")
    return unidecode(x.strip().upper())


def pad_id_comune(series, width=6):
    """Zero-pad an ID_COMUNE column to `width` digits (e.g. 22001 -> '022001').

    Missing / unmapped values (NaN) are left untouched. Works regardless of
    whether the column arrives as int, float (common when NaNs are present),
    or string dtype.
    """
    def _pad(x):
        if pd.isna(x):
            return x
        return str(int(x)).zfill(width)

    return series.apply(_pad)


def _remove_provincia(df, comune_col="comune", upper=False):
    """Drop rows whose comune starts with 'PROVINCIA', logging what gets removed."""
    series = df[comune_col].str.upper() if upper else df[comune_col]
    mask = series.str.startswith("PROVINCIA")
    if mask.any():
        logging.info(
            f"Comune {df.loc[mask, comune_col].unique()} is a PROVINCIA, removing it from the analysis"
        )
        df = df[~mask]
    return df


def _to_data_location(df, date_col, drop_cols=None):
    """Standardize a phenomenon dataframe to DATA/LOCATION column naming.

    date_col: name of the column holding the time dimension (e.g. "anno" or "date").
    drop_cols: optional columns to drop before returning (e.g. a redundant "anno"
    column once the daily "date" column is promoted to DATA).
    """
    df = df.drop(columns=drop_cols) if drop_cols else df
    return df.rename(columns={date_col: "DATA", "comune": "LOCATION"})


def compute_arrivi_trentino():
    arrivi_trentino = pd.read_csv(get_s3("arrivi_trentino_ISPAT.csv"))
    arrivi_trentino.rename(columns={"Anno": "anno", "Ambito": "comune"}, inplace=True)
    arrivi_trentino = pd.melt(
        arrivi_trentino,
        id_vars="comune",
        value_vars=["2021", "2022", "2023", "2024"],
        value_name="arrivi",
        var_name="anno",
    )
    arrivi_trentino["anno"] = arrivi_trentino["anno"].astype(int)
    arrivi_trentino = arrivi_trentino.sort_values(by=["comune", "anno"]).reset_index(
        drop=True
    )

    arrivi_trentino = _remove_provincia(arrivi_trentino, upper=True)
    arrivi_trentino = _to_data_location(arrivi_trentino, date_col="anno")

    return arrivi_trentino

def compute_presenze_trentino(mapping_comuni, how = "uniform", distribution = None):
    
    presenze_ispat = pd.read_csv(get_s3("presenze_Trentino_ISPAT.csv"))
    presenze_alb_xalb = pd.read_csv(get_s3("presenze_Trentino_ISPAT_alb_xalb.csv"))
    with open(PATH_MAPPING / "map_comuni_into_apt.json") as f:
        json_apt = json.load(f)

    ## Adjust the datasets
    ## presenze_ispat
    presenze_ispat.rename(
        columns={"Ambito": "comune", "Presenze": "presenze"}, inplace=True
    )
    presenze_ispat["Anno"] = presenze_ispat["Anno"].astype(int)
    presenze_ispat["data"] = pd.to_datetime(
        {"year": presenze_ispat["Anno"], "month": presenze_ispat["Mese"], "day": 1}
    )
    presenze_ispat.drop(columns=["Anno", "Mese"], inplace=True)
    presenze_ispat["ID_COMUNE"] = presenze_ispat["comune"].map(json_apt).apply(
        lambda x: [int(i) for i in x] if isinstance(x, list) else x
    )

    presenze_ispat = presenze_ispat.sort_values(by=["comune", "data"]).reset_index(
        drop=True
    )
    presenze_ispat = _remove_provincia(presenze_ispat, upper=True)

    ## presenze_ispat_alb_xalb
    presenze_alb_xalb["Anno"] = presenze_alb_xalb["Anno"].astype(int)
    presenze_alb_xalb["data"] = pd.to_datetime(
        {
            "year": presenze_alb_xalb["Anno"],
            "month": presenze_alb_xalb["Mese"],
            "day": 1,
        }
    )
    presenze_alb_xalb.drop(columns=["Anno", "Mese"], inplace=True)
    presenze_alb_xalb = presenze_alb_xalb.sort_values("data")
    values_mapping = list(mapping_comuni.values())

    presenze_alb_xalb["ID_COMUNE"] = [values_mapping] * len(presenze_alb_xalb)

    ## disaggregation
    presenze_ispat = disaggregate_apt_presences(
        presenze_ispat,
        presenze_alb_xalb,
        mapping_comuni,
        how=how,
        distribution=distribution,
    )

    df = _to_data_location(
        presenze_ispat,
        date_col="data",
    )
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime('%Y-%m-%d')
    return df


def compute_popolazione():
    json_popolazione = json.load(open(PATH_MAPPING / "popolazione_Trento.json"))
    popolazione_df = get_dataframe("popolazione_2020_2024")
    popolazione_df["comune"] = popolazione_df["comune"].apply(
        lambda x: customize_unidecode(x)
    )
    popolazione_df["ID_COMUNE"] = popolazione_df["comune"].map(json_popolazione)
    popolazione_df = _remove_provincia(popolazione_df)
    popolazione_df = _to_data_location(popolazione_df, date_col="anno")

    popolazione_df["ID_COMUNE"] = pad_id_comune(popolazione_df["ID_COMUNE"])

    return popolazione_df


# Explicit overrides for comuni whose official Italian name differs from
# a naive "before the dash" split of the bilingual name in the source CSV.
COMUNE_NAME_OVERRIDES = {
    "CAMPITELLO DI FASSA-CIAMPEDEL": "CAMPITELLO DI FASSA",
    "CAMPODENNO": "CAMPODENNO",  # no dash present, check exact spelling/accents in mapping
    "CANAL SAN BOVO": "CANAL SAN BOVO",
    "CANAZEI-CIANACEI": "CANAZEI",
    "FIEROZZO-VLAROTZ": "FIEROZZO",
    "FRASSILONGO-GARAIT": "FRASSILONGO",
    "LUSERNA-LUSERN": "LUSERNA",
    "MAZZIN-MAZIN": "MAZZIN",
    "MOENA-MOENA": "MOENA",
    "PALU DEL FERSINA-PALAI EN BERSNTOL": "PALU DEL FERSINA",
    "SAN GIOVANNI DI FASSA-SEN JAN": "SAN GIOVANNI DI FASSA",
    "SORAGA DI FASSA-SORAGA": "SORAGA DI FASSA",
}


def compute_strutture(mapping_comuni):
    strutture_ospitalita_trentino_df = pd.read_csv(get_s3("Annuario-TavXIII-per-comune-csv.csv"))
    json_strutture = PATH_MAPPING / "strutture_ospitalita_Trento_2020.json"
    json_strutture = json.load(open(json_strutture))

    ## take years from 2020
    strutture_ospitalita_from_2020 = strutture_ospitalita_trentino_df[
        strutture_ospitalita_trentino_df["anno"] > 2019
    ].copy()
    strutture_ospitalita_from_2020["comune"] = strutture_ospitalita_from_2020[
        "comune"
    ].apply(lambda x: customize_unidecode(x).replace("0", "-"))

    strutture_ospitalita_from_2020["ID_COMUNE"] = strutture_ospitalita_from_2020[
        "comune"
    ].map(json_strutture)

    strutture_ospitalita_from_2020 = _remove_provincia(strutture_ospitalita_from_2020)

    ## Standardize to the common DATA / LOCATION schema
    strutture_ospitalita_from_2020 = _to_data_location(
        strutture_ospitalita_from_2020, date_col="anno"
    )

    CATEGORIA_TOT_CONVENZIONALI = "tot convenzionali strutture"
    CATEGORIA_ALLOGGI_PRIVATI = "all. privati numero"
    CATEGORIA_TOT_CONVENZIONALI_LETTI = "tot convenzionali posti_letto"
    CATEGORIA_ALLOGGI_PRIVATI_LETTI = "all. privati posti_letto"

    strutture_ospitalita_from_2020["tot_strutture"] = (
        strutture_ospitalita_from_2020[CATEGORIA_TOT_CONVENZIONALI]
        + strutture_ospitalita_from_2020[CATEGORIA_ALLOGGI_PRIVATI]
    )
    strutture_ospitalita_from_2020["tot_strutture_non_conv"] = (
        strutture_ospitalita_from_2020[CATEGORIA_ALLOGGI_PRIVATI]
    )
    strutture_ospitalita_from_2020["tot_postiletto"] = (
        strutture_ospitalita_from_2020[CATEGORIA_TOT_CONVENZIONALI_LETTI]
        + strutture_ospitalita_from_2020[CATEGORIA_ALLOGGI_PRIVATI_LETTI]
    )
    strutture_ospitalita_from_2020["tot_postiletto_non_conv"] = (
        strutture_ospitalita_from_2020[CATEGORIA_ALLOGGI_PRIVATI_LETTI]
    )

    # Try direct match first, then fall back to the override table
    strutture_ospitalita_from_2020["ID_COMUNE"] = strutture_ospitalita_from_2020[
        "LOCATION"
    ].map(mapping_comuni)

    unmatched_mask = strutture_ospitalita_from_2020["ID_COMUNE"].isna()
    if unmatched_mask.any():
        fallback_names = strutture_ospitalita_from_2020.loc[
            unmatched_mask, "LOCATION"
        ].map(COMUNE_NAME_OVERRIDES)
        strutture_ospitalita_from_2020.loc[unmatched_mask, "ID_COMUNE"] = (
            fallback_names.map(mapping_comuni)
        )

    strutture_ospitalita_from_2020["ID_COMUNE"] = pad_id_comune(
        strutture_ospitalita_from_2020["ID_COMUNE"]
    )

    # Report anything still unresolved
    still_missing = strutture_ospitalita_from_2020[
        strutture_ospitalita_from_2020["ID_COMUNE"].isna()
    ]["LOCATION"].unique()
    if len(still_missing) > 0:
        print(
            f"[compute_strutture] WARNING: could not find ID_COMUNE for "
            f"{len(still_missing)} comune(s): {sorted(still_missing)}"
        )

    return strutture_ospitalita_from_2020[
        [
            "DATA",
            "LOCATION",
            "ID_COMUNE",
            "tot_postiletto",
            "tot_postiletto_non_conv",
            "tot_strutture",
            "tot_strutture_non_conv",
        ]
    ]

def split_cols_unif(df, id_to_comune, cols_split=["presenze"]):
    """Function which splits the presences uniformly between multiple ID_COMUNE"""
    rows = []

    for _, row in df.iterrows():
        ids = row["ID_COMUNE"]

        if isinstance(ids, int):
            new_row = row.copy()
            new_row["comune"] = id_to_comune.get(ids)
            rows.append(new_row)
            continue

        if len(ids) == 1:
            new_row = row.copy()
            new_row["ID_COMUNE"] = ids[0]
            new_row["comune"] = id_to_comune.get(ids[0])
            rows.append(new_row)
            continue

        n = len(ids)

        for i, ID_COMUNE in enumerate(ids):
            new_row = row.copy()
            new_row["ID_COMUNE"] = ID_COMUNE
            new_row["comune"] = id_to_comune.get(ID_COMUNE)

            for c in cols_split:
                total = int(row[c])
                base = total // n
                remainder = total % n
                new_row[c] = base + (1 if i < remainder else 0)
            rows.append(new_row)
    return pd.DataFrame(rows)

def split_data_province(df, mapping_comuni):
    """Function which splits the data between all the comuni of the province, uniformly"""
    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    df = df.set_index("data")
    n = len(mapping_comuni)
    df["base_alb"] = df["presenze_alb"] // n
    df["rem_alb"] = df["presenze_alb"] % n
    
    df["base_xalb"] = df["presenze_xalb"] // n
    df["rem_xalb"] = df["presenze_xalb"] % n
    
    df = df.reset_index()
    
    df_exploded = df.explode("ID_COMUNE")
    
    df_exploded["idx_comune"] = df_exploded.groupby("data").cumcount()
    
    df_exploded["presenze_alb"] = df_exploded["base_alb"] + (df_exploded["idx_comune"] < df_exploded["rem_alb"]).astype(int)
    df_exploded["presenze_xalb"] = df_exploded["base_xalb"] + (df_exploded["idx_comune"] < df_exploded["rem_xalb"]).astype(int)
    df_exploded["comune"] = df_exploded["ID_COMUNE"].map(id_to_comune)

    df_final = df_exploded[[ "data", "ID_COMUNE", "comune", "presenze_xalb"]]    # "presenze_alb"
    return df_final


def split_presences_distributional(
    df: pd.DataFrame,
    distribution: pd.DataFrame,
    cols = ["presenze"],
    *,
    group_col: str = "LOCATION",
    time_col: str = "DATA",
    id_col: str = "ID_COMUNE",
    weight_col: str = "presenze",
    period: str = "M",
) -> pd.DataFrame:
    """
    Distribuisce le presenze ISPAT (mensili, per APT) su base
    giornaliera e comunale, usando come "forma" di riferimento
    la distribuzione osservata nei dati Vodafone (giornalieri, per comune).
    """
    df = df.copy()
    distribution = distribution.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df["_PERIOD"] = df[time_col].dt.to_period(period)

    distribution["_PERIOD"] = pd.to_datetime(distribution[time_col]).dt.to_period(period)
    distribution[id_col] = distribution[id_col].astype(int)

    df_exploded = df.rename(
        columns={group_col: "_GROUP"}
    ).explode(id_col)
    df_exploded[id_col] = df_exploded[id_col].astype(int)

    # Per ogni comune dell'APT, prende TUTTI i giorni di quel mese da Vodafone
    merged = pd.merge(
        df_exploded.drop(columns = [time_col]),
        distribution.rename(
            columns={weight_col: "presenze_vodafone"}),
        on=["_PERIOD", id_col],
    )
    if len(merged[merged.isna().any(axis=1)]) > 0:
        logging.warning(
            f"Found {merged[merged.isna().any(axis=1)].shape[0]} rows with missing values after merging ISPAT and Vodafone data"
        )
    merged["_denom"] = merged.groupby(["_GROUP", "_PERIOD"])["presenze_vodafone"].transform("sum")
    merged["weight"] = merged["presenze_vodafone"] / merged["_denom"]
    for c in cols:
        merged[f"{c}_distributed"] = (merged[c] * merged["weight"]).round()
    return merged.drop(columns=["_PERIOD", "_denom", "weight", "_GROUP",*cols])


## DISAGGREGATION FUNCTIONS 

def disaggregate_apt_presences(
        df, df_xalb, mapping_comuni, how = "uniform", distribution = None
):
    """
    Expand rows with multiple ID_COMUNEs into one row per municipality.
    dividing presences equally between APT locations.
    WARNING: in this case, there are two approximations of alberghieri. We mantain the columns relative to the thinner granularity (in this case, APT is kept, at the cost of province) 
    TODO: generalize this function without columns hardcoded
    """
    # mapping_comuni
    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    df_xalb.rename(columns = {"Presenze alberghi": "presenze_alb", "Presenze extra-alberghi": "presenze_xalb"},inplace = True)
    if how == "uniform":
        presences = split_cols_unif(df, id_to_comune)
        presences_xalb = split_data_province(df_xalb, mapping_comuni)
        presences = presences.merge(
            presences_xalb, 
            on=["data", "ID_COMUNE", "comune"], 
            how="left"
        )
    elif how == "distributional":
        assert not distribution is None, "Distribution must be provided for distributional disaggregation"
        df.rename(columns={"comune":"LOCATION", "data":"DATA", "presenze": "presenze_alb"}, inplace = True)
        presences = split_presences_distributional(df, distribution, cols = ["presenze_alb"])
        df_xalb["LOCATION"] = "PROVINCIA"
        df_xalb.rename(columns={"data":"DATA"}, inplace = True)
        presences_xalb = split_presences_distributional(
            df_xalb, distribution, 
            cols = ["presenze_alb", "presenze_xalb"]
        )
    else: 
        raise ValueError(f"Unknown disaggregation method: {how}")
    return presences.merge(
        presences_xalb.drop(columns={"LOCATION", "presenze_alb_distributed"}), 
        on=["DATA", "ID_COMUNE", "presenze_vodafone"],
        how="outer"
    ).drop(columns={"LOCATION"})


def disaggregate_vodafone_presences(df, mapping_comuni, how="uniform"):
    """
    Expand rows with multiple ID_COMUNEs into one row per municipality.

    The presenze are divided as evenly as possible while preserving the total.

    NOTE: This is a temporary workaround, better ways to distribute presences should be implemented.
    """

    # mapping_comuni is keyed name -> id; we need the reverse (id -> name) here.
    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    if how == "uniform":
        presences = split_cols_unif(df, id_to_comune)
    else:
        raise ValueError(f"Unknown disaggregation method: {how}")
    return pd.DataFrame(presences)


def compute_vodafone_attendences(mapping_comuni):
    vodafone_attendences_df = get_dataframe("vodafone_attendences")

    with open(PATH_MAPPING / "vodafone_Trento.json") as f:
        json_vodafone = json.load(f)

    geojson_comuni_json_data = geopd.read_file(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))
    location_map = geojson_comuni_json_data.set_index("id")["name"].str.upper().to_dict()

    vodafone_attendences_df["comune"] = vodafone_attendences_df["locId"].map(
        location_map
    )

    vodafone_attendences_df["ID_COMUNE"] = vodafone_attendences_df["comune"].map(
        json_vodafone
    )

    # Unify Vigo di Fassa and Pozza di Fassa
    logging.info(
        "Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)"
    )

    mask = vodafone_attendences_df["comune"].isin(["VIGO DI FASSA", "POZZA DI FASSA"])

    vodafone_attendences_df.loc[mask, "comune"] = "SAN GIOVANNI DI FASSA"
    vodafone_attendences_df.loc[mask, "ID_COMUNE"] = [[22250]] * mask.sum()

    # Keep only tourist presences at municipality level
    df = vodafone_attendences_df[
        (vodafone_attendences_df["userProfile"] == "TOURIST")
        & (vodafone_attendences_df["locType"] == "TN_MKT_AL_3")
        & (vodafone_attendences_df["comune"].notna())
    ].copy()

    # Aggregate daily presences by municipality
    aggregations = {
        "ID_COMUNE": "first",
        "value": "sum",
    }

    df = (
        df.groupby(["date", "comune"])
        .agg(aggregations)
        .reset_index()
        .rename(columns={"value": "presenze"})
    )

    df = disaggregate_vodafone_presences(df, mapping_comuni)

    # Standardize schema
    df = _to_data_location(
        df,
        date_col="date",
    )

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return df


def create_mapping(df):
    """Utility function which creates mapping ISTAT IDS <> IDs """

    extra_mapping = {
        'BENESELLO + CALLIANO + VOLANO' : 'BESENELLO + CALLIANO + VOLANO',
        'BORGO CHIESE + CASTEL CONDINO + PIEVE DI BONO-PREZ' : 'BORGO CHIESE + CASTEL CONDINO + PIEVE DI BONO-PREZZO',
        'PERGINE VALSUGANA + VIGNOLA-FALESINA (NORD)': 'PERGINE VALSUGANA + VIGNOLA-FALESINA',
        'PERGINE VALSUGANA + VIGNOLA-FALESINA (SUD)': 'PERGINE VALSUGANA + VIGNOLA-FALESINA',
        'RIVA DEL GARDA (PAESE)' : 'RIVA DEL GARDA',
        'RIVA DEL GARDA (SUL LAGO)': 'RIVA DEL GARDA',
        'ROVERETO (BORGO SACCO)': 'ROVERETO',
        'ROVERETO (CENTRO)': 'ROVERETO',
        'ROVERETO (LIZZANA - OSPEDALE)': 'ROVERETO',
        'ROVERETO (MARCO)': 'ROVERETO',
        'ROVERETO (NORIGLIO)': 'ROVERETO',
        'SANT\'ORSOLA TERME + FRASSILONGO + PALU\' DEL FERSIN': 'SANT\'ORSOLA TERME + FRASSILONGO + PALU\' DEL FERSINA',
        'TN CENTRO': 'TRENTO',
        'TN EST': 'TRENTO',
        'TN NORD': 'TRENTO',
        'TN OLTRE ADIGE NORD': 'TRENTO',
        'TN OLTRE ADIGE SUD': 'TRENTO',
        'TN SUD': 'TRENTO'
    }

    with open(PATH_MAPPING / "vodafone_Trento.json") as f: 
        mapping_comuni_voda = json.load(f)
    df['codice_istat_voda'] = df['comune'].str.upper().str.strip().map(mapping_comuni_voda)

    df.loc[df['codice_istat_voda'].isna(), 'codice_istat_voda'] = (
        df.loc[df['codice_istat_voda'].isna(), 'comune']
        .str.upper().str.strip()
        .map(extra_mapping)
        .str.upper().str.strip()
        .map(mapping_comuni_voda)
    )

    mask = df["comune"].isin(["VIGO DI FASSA", "POZZA DI FASSA"])
    df.loc[mask, "comune"] = "SAN GIOVANNI DI FASSA"
    for idx in df.index[mask]:
        df.at[idx, "codice_istat_voda"] = [22250]
    return dict(zip(df['ID'], df['codice_istat_voda']))


def compute_flussi_trentino(mapping_comuni):
    df_ = pd.read_parquet(PATH_RAW_DATA / "grid_all_columns__.parquet")
    df_u = pd.read_parquet(PATH_RAW_DATA / "grid_all_columns_user.parquet")

    cols = ['AREA_ID', 'AREA_LABEL', 
            'hotspot_level_tot_in_flows_t_0_0_w_all_days_d_', 'tot_in_flows_t_0_0_w_all_days_d_', 'hotspot_level_tot_out_flows_t_0_0_w_all_days_d_', 'tot_out_flows_t_0_0_w_all_days_d_']
    ## Mappatura colonne dati parquet completo
    df__map = {
        'AREA_ID': 'ID',
        'AREA_LABEL': 'comune',
        'tot_in_flows_t_0_0_w_all_days_d_': 'FLOWS_IN',
        'tot_out_flows_t_0_0_w_all_days_d_': 'FLOWS_OUT',
        'hotspot_level_tot_in_flows_t_0_0_w_all_days_d_': 'LEVEL_IN',
        'hotspot_level_tot_out_flows_t_0_0_w_all_days_d_': 'LEVEL_OUT',
    }

    df_flussi_all = df_[cols].copy()
    df_flussi_all = df_flussi_all[df_flussi_all['AREA_ID'].str.startswith('ITA.04.022.', na=False)]

    # TODO: MANAGE DIFFERENTLY (this operation of multiplying was done in original file)
    df_flussi_all['tot_in_flows_t_0_0_w_all_days_d_'] *= 4
    df_flussi_all['tot_out_flows_t_0_0_w_all_days_d_'] *= 4

    df_flussi_all.rename(columns = df__map, inplace=True)
    df_flussi_all['comune'] = df_flussi_all['comune'].str.upper()

    ## Mappatura colonne dati Utenti / Escursionisti / Turisti 
    cols_user = ['AREA_ID', 'AREA_LABEL',
                 'hotspot_level_tot_in_flows_TOURIST_t_0_0_w_all_days_d_','tot_in_flows_TOURIST_t_0_0_w_all_days_d_','hotspot_level_tot_out_flows_TOURIST_t_0_0_w_all_days_d_','tot_out_flows_TOURIST_t_0_0_w_all_days_d_','hotspot_level_tot_in_flows_VISITOR_t_0_0_w_all_days_d_','tot_in_flows_VISITOR_t_0_0_w_all_days_d_','hotspot_level_tot_out_flows_VISITOR_t_0_0_w_all_days_d_','tot_out_flows_VISITOR_t_0_0_w_all_days_d_']
    df_u_map = {
        'AREA_ID': 'ID',
        'AREA_LABEL': 'comune',
        'hotspot_level_tot_in_flows_TOURIST_t_0_0_w_all_days_d_':'LEVEL_IN_TOURISTS',
        'tot_in_flows_TOURIST_t_0_0_w_all_days_d_':'FLOWS_IN_TOURISTS',
        'hotspot_level_tot_out_flows_TOURIST_t_0_0_w_all_days_d_':'LEVEL_OUT_TOURISTS',
        'tot_out_flows_TOURIST_t_0_0_w_all_days_d_':'FLOWS_OUT_TOURISTS',
        'hotspot_level_tot_in_flows_VISITOR_t_0_0_w_all_days_d_':'LEVEL_IN_VISITORS',
        'tot_in_flows_VISITOR_t_0_0_w_all_days_d_': 'FLOWS_IN_VISITORS',
        'hotspot_level_tot_out_flows_VISITOR_t_0_0_w_all_days_d_':'LEVEL_OUT_VISITORS',
        'tot_out_flows_VISITOR_t_0_0_w_all_days_d_':'FLOWS_OUT_VISITORS'
        }

    df_flussi_all_user = df_u[cols_user].copy()
    df_flussi_all_user = df_flussi_all_user[df_flussi_all_user['AREA_ID'].str.startswith('ITA.04.022.', na=False)]
    df_flussi_all_user.rename(columns = df_u_map, inplace=True)
    df_flussi_all_user['comune'] = df_flussi_all_user['comune'].str.upper()

    df_merged = pd.merge(df_flussi_all, df_flussi_all_user, on=['ID', 'comune'], how='outer', indicator=True)
    if len(df_merged[df_merged['_merge'] != 'both']) > 0:
        logging.warning("WARNING: discrepancies found in IDs: ",len(df_merged[df_merged['_merge'] != 'both']))
    df_merged['DATA'] = 2024
    id_map = create_mapping(df_flussi_all_user[['ID', 'comune']])
    df_merged["ID_COMUNE"] = df_merged["ID"].map(id_map)

    value_cols = ['FLOWS_IN', 'FLOWS_OUT', 'FLOWS_IN_TOURISTS', 'FLOWS_OUT_TOURISTS',
                    'FLOWS_IN_VISITORS', 'FLOWS_OUT_VISITORS']
    level_cols = ['LEVEL_IN', 'LEVEL_OUT', 'LEVEL_IN_TOURISTS', 'LEVEL_OUT_TOURISTS',
                  'LEVEL_IN_VISITORS', 'LEVEL_OUT_VISITORS']
    df_merged = split_cols_unif(
        df_merged, 
        id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()},
        cols_split = value_cols)
    agg_dict = {
        **{col: 'sum' for col in value_cols},
        **{col: 'median' for col in level_cols}
    }
    df_merged = df_merged.groupby(['DATA', 'ID_COMUNE', 'comune']).agg(agg_dict).reset_index() # For the moment, use median for the level 
    df_merged["ID_COMUNE"] = pad_id_comune(df_merged["ID_COMUNE"])
    return df_merged


def compute_phenomenon_dataframes():
    """Loads and prepares the base "phenomenon" dataframes.

    Returns a dict with keys:
      "phen_strutture_ospitalita", "phen_popolazione",
      "phen_vodafone_attendences", "phen_arrivi_trentino"
    Each value is a dataframe standardized to DATA/LOCATION (+ ID, + the
    phenomenon's own value columns). Any ID_COMUNE column is zero-padded to
    6 digits (e.g. 22001 -> "022001").
    """

    with open(PATH_MAPPING / "mapping_comuni_ISTAT.json") as f:
        mapping_comuni = json.load(f)

    popolazione_df = compute_popolazione()
    strutture_ospitalita_from_2020 = compute_strutture(mapping_comuni)
    vodafone_attendences_df = compute_vodafone_attendences(mapping_comuni)
    arrivi_trentino = compute_arrivi_trentino()
    presenze_df = compute_presenze_trentino(
        mapping_comuni, how="distributional", distribution=vodafone_attendences_df
    )
    flussi_df = compute_flussi_trentino(mapping_comuni)

    return {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_ospitalita_from_2020,
        "phen_arrivi": arrivi_trentino,
        "phen_presenze": presenze_df,
        "phen_flussi": flussi_df
       }


def main():
    logging.info(f"## Computing phenomenon dataframes")
    dict_dfs = compute_phenomenon_dataframes()
    logging.info("## Uploading phenomenon dataframes...")
    for key, value in dict_dfs.items():
        log_dataframe(value.reset_index(), key)
    logging.info("## Saved.")

def local():
    """Saves locally the results"""
    logging.info("## Computing phenomenon dataframes...")
    dict_dfs = compute_phenomenon_dataframes()
    logging.info("## Saving phenomenon dataframes...")
    for key, value in dict_dfs.items():
        put_dataframe(value, key, type="parquet", path = PATH_AIXPA_INDEX_DFS)
    logging.info("## Saved.")

if __name__ == "__main__":
    local()