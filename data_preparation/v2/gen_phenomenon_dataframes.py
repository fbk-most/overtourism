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
from utils import get_dataframe, get_s3, log_dataframe, put_dataframe, get_json_s3
from disaggregation import disaggregate

logging.basicConfig(level=logging.INFO)

PATH_OVERTOURISM = Path(__file__).parents[3].resolve() 
PATH_AIXPA_INDEX_DFS = PATH_OVERTOURISM / 'overtourism' / 'overtourism' / 'overtourism' / 'database' / 'index_data_v2'
PATH_AIXPA_INDEX_DFS.mkdir(parents=True, exist_ok=True)

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


FLUSSI_VALUE_COLS = [
    "FLOWS_IN", "FLOWS_OUT", "FLOWS_IN_TOURISTS", "FLOWS_OUT_TOURISTS",
    "FLOWS_IN_VISITORS", "FLOWS_OUT_VISITORS",
]
FLUSSI_LEVEL_COLS = [
    "LEVEL_IN", "LEVEL_OUT", "LEVEL_IN_TOURISTS", "LEVEL_OUT_TOURISTS",
    "LEVEL_IN_VISITORS", "LEVEL_OUT_VISITORS",
]


## UTILS FUNCTIONS
## Some functions for decoding / padding / cleaning 
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
    
    df = df.copy()
    logging.info("Downloading mapping_ids/mapping_comuni_into_vodafone_Trento.json from S3...")
    mapping_comuni_voda = get_json_s3("mapping_ids/mapping_comuni_into_vodafone_Trento.json")
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

def resolve_id_comune(name, mapping_comuni, overrides=COMUNE_NAME_OVERRIDES):
    """Map a comune name to its ISTAT ID, falling back to the bilingual-name overrides."""
    id_comune = mapping_comuni.get(name)
    if id_comune is None and name in overrides:
        id_comune = mapping_comuni.get(overrides[name])
    return id_comune


## COMPUTATION 
## Functions to compute phenomena dataframes 
def compute_arrivi_trentino(years = ["2021", "2022", "2023", "2024"]):
    logging.info("Downloading arrivi_trentino_ISPAT.csv from S3...")
    arrivi_trentino = pd.read_csv(get_s3("arrivi_trentino_ISPAT.csv"))
    arrivi_trentino.rename(columns={"Anno": "anno", "Ambito": "comune"}, inplace=True)
    arrivi_trentino = pd.melt(
        arrivi_trentino,
        id_vars="comune",
        value_vars=years,
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


def compute_presenze_trentino(mapping_comuni, how="uniform", distribution=None):
    logging.info("Downloading presenze_Trentino_ISPAT.csv from S3...")
    presenze_ispat = pd.read_csv(get_s3("presenze_Trentino_ISPAT.csv"))
    logging.info("Downloading presenze_Trentino_ISPAT_alb_xalb.csv from S3...")
    presenze_alb_xalb = pd.read_csv(get_s3("presenze_Trentino_ISPAT_alb_xalb.csv"))
    logging.info("Downloading mapping_ids/map_comuni_into_apt.json from S3...")
    json_apt = get_json_s3("mapping_ids/map_comuni_into_apt.json")

    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    ## Adjust the datasets
    ## presenze_ispat
    ## APT level: monthly presences by ambito
    presenze_ispat.rename(
        columns={"Ambito": "comune", "Presenze": "presenze_alb"}, inplace=True
    )
    presenze_ispat["data"] = pd.to_datetime(
        {
            "year": presenze_ispat["Anno"].astype(int),
            "month": presenze_ispat["Mese"],
            "day": 1,
        }
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
    ## Province level: monthly alberghiero / extra-alberghiero split
    presenze_ispat = _to_data_location(presenze_ispat, date_col="data")

    presenze_alb_xalb.rename(
        columns={
            "Presenze alberghi": "presenze_alb",
            "Presenze extra-alberghi": "presenze_xalb",
        },
        inplace=True,
    )
    presenze_alb_xalb["data"] = pd.to_datetime(
        {
            "year": presenze_alb_xalb["Anno"].astype(int),
            "month": presenze_alb_xalb["Mese"],
            "day": 1,
        }
    )
    presenze_alb_xalb.drop(columns=["Anno", "Mese"], inplace=True)
    presenze_alb_xalb = presenze_alb_xalb.sort_values("data").reset_index(drop=True)
    presenze_alb_xalb["comune"] = "PROVINCIA"
    presenze_alb_xalb["ID_COMUNE"] = [list(mapping_comuni.values())] * len(presenze_alb_xalb)
    presenze_alb_xalb = _to_data_location(presenze_alb_xalb, date_col="data")

    ## Monthly x APT -> daily x comune
    kwargs = dict(axis="both", freq_from="M", freq_to="D", id_to_name=id_to_comune)
    if how == "distributional":
        assert distribution is not None, "Distribution required for 'distributional' disaggregation"
        kwargs.update(
            space_weights=distribution,
            space_weight_col="presenze",
            space_time_freq="M",
            time_weights=distribution,
            time_weight_col="presenze",
        )
    elif how != "uniform":
        raise ValueError(f"Unknown disaggregation method: {how}")

    presenze = disaggregate(presenze_ispat, cols=["presenze_alb"], **kwargs)
    presenze_prov = disaggregate(
        presenze_alb_xalb, cols=["presenze_alb", "presenze_xalb"], **kwargs
    )

    # presenze_alb is kept at the finer (APT) granularity, only the
    # extra-alberghiero column is taken from the province-level estimate
    df = presenze.merge(
        presenze_prov[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="outer",
    )
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    return df


def compute_popolazione(mapping_comuni):
    logging.info("Downloading dataframe 'popolazione_2020_2024'...")
    popolazione_df = get_dataframe("popolazione_2020_2024")
    popolazione_df["comune"] = popolazione_df["comune"].apply(customize_unidecode)
    popolazione_df["ID_COMUNE"] = popolazione_df["comune"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    popolazione_df = _remove_provincia(popolazione_df)
    popolazione_df = _to_data_location(popolazione_df, date_col="anno")
    popolazione_df["ID_COMUNE"] = pad_id_comune(popolazione_df["ID_COMUNE"])
    return popolazione_df


def compute_strutture(mapping_comuni):
    logging.info("Downloading Annuario-TavXIII-per-comune-csv.csv from S3...")
    strutture_ospitalita_trentino_df = pd.read_csv(get_s3("Annuario-TavXIII-per-comune-csv.csv"))
    strutture_ospitalita_from_2020 = strutture_ospitalita_trentino_df[
        strutture_ospitalita_trentino_df["anno"] > 2019
    ].copy()  # consideriamo solo anni successivi, a causa di aggregazioni comunali
    strutture_ospitalita_from_2020["comune"] = strutture_ospitalita_from_2020["comune"].apply(
        lambda x: customize_unidecode(x).replace("0", "-")
    )
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
    strutture_ospitalita_from_2020["ID_COMUNE"] = strutture_ospitalita_from_2020["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    strutture_ospitalita_from_2020["ID_COMUNE"] = pad_id_comune(strutture_ospitalita_from_2020["ID_COMUNE"])

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


def compute_vodafone_attendences(
    mapping_comuni, how="uniform", distribution=None,
    weight_col="popolazione", weight_freq="Y",
):
    logging.info("Downloading dataframe 'vodafone_attendences'...")
    vodafone_attendences_df = get_dataframe("vodafone_attendences")

    logging.info("Downloading mapping_ids/mapping_comuni_into_vodafone_Trento.json from S3...")
    json_vodafone = get_json_s3("mapping_ids/mapping_comuni_into_vodafone_Trento.json")

    logging.info("Downloading TRENTINO-comuni_Vodafone_2023.geojson from S3...")
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
    df = (
        df.groupby(["date", "comune"])
        .agg({"ID_COMUNE": "first", "value": "sum"})
        .reset_index()
        .rename(columns={"value": "presenze"})
    )
    df = _to_data_location(df, date_col="date")

    ## disaggregation spatial only, data is already daily
    kwargs = dict(
        axis="space",
        id_to_name={id_comune: name for name, id_comune in mapping_comuni.items()},
    )
    if how == "distributional":
        assert distribution is not None, "Distribution required for 'distributional' disaggregation"
        kwargs.update(
            space_weights=distribution,
            space_weight_col=weight_col,
            space_time_freq=weight_freq,
        )
    elif how != "uniform":
        raise ValueError(f"Unknown disaggregation method: {how}")

    df = disaggregate(df, cols=["presenze"], **kwargs)

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    return df


def compute_flussi_trentino(mapping_comuni):
    # NOTE: The following files are generated by the diffusion process. For the moment they are uploaded on atlas, TODO: decide whether integrate the process or mantain it external
    logging.info("Downloading grid_all_columns__.parquet from S3...")
    df_ = pd.read_parquet(get_s3("grid_all_columns__.parquet"))   
    logging.info("Downloading grid_all_columns_user.parquet from S3...")
    df_u = pd.read_parquet(get_s3("grid_all_columns_user.parquet"))

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

    value_cols, level_cols = FLUSSI_VALUE_COLS, FLUSSI_LEVEL_COLS
    df_merged = disaggregate(
        df_merged,
        cols=value_cols,
        axis="space",
        group_col="comune",
        id_to_name={id_comune: name for name, id_comune in mapping_comuni.items()},
    )

    agg_dict = {
        **{col: 'sum' for col in value_cols},
        **{col: 'median' for col in level_cols}
    }
    df_merged = df_merged.groupby(['DATA', 'ID_COMUNE', 'comune']).agg(agg_dict).reset_index() # For the moment, use median for the level 
    df_merged["ID_COMUNE"] = pad_id_comune(df_merged["ID_COMUNE"])
    return df_merged


def compute_flussi_2023_temp(flussi_df):
    """Compute a temporary version of the flussi dataframe for 2023, using the 2024 data as a proxy.
    NOTE: IMPORTANT: This is a temporary solution, and should be replaced with actual data when available."""
    flussi_temp_2023 = flussi_df.copy()
    flussi_temp_2023["DATA"] = 2023
    return flussi_temp_2023


## MAIN computation of phenomena 
def compute_phenomenon_dataframes():
    """Loads and prepares the base "phenomenon" dataframes.

    Returns a dict with keys:
      "phen_strutture_ospitalita", "phen_popolazione",
      "phen_vodafone_attendences", "phen_arrivi_trentino"
    Each value is a dataframe standardized to DATA/LOCATION (+ ID, + the
    phenomenon's own value columns). Any ID_COMUNE column is zero-padded to
    6 digits (e.g. 22001 -> "022001").
    """
    logging.info("Downloading mapping_ids/mapping_comuni_ISTAT.json from S3...")
    mapping_comuni = get_json_s3("mapping_ids/mapping_comuni_ISTAT.json")
    popolazione_df = compute_popolazione(mapping_comuni)
    strutture_ospitalita_from_2020 = compute_strutture(mapping_comuni)
    vodafone_attendences_df = compute_vodafone_attendences(mapping_comuni)
    arrivi_trentino = compute_arrivi_trentino()
    presenze_df = compute_presenze_trentino(
        mapping_comuni, how="distributional", distribution=vodafone_attendences_df
    )
    flussi_df = compute_flussi_trentino(mapping_comuni)
    phen_flussi_temp_2023 = compute_flussi_2023_temp(flussi_df)

    return {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_ospitalita_from_2020,
        "phen_arrivi": arrivi_trentino,
        "phen_presenze": presenze_df,
        "phen_flussi": flussi_df,
        "phen_flussi_temp_2023": phen_flussi_temp_2023
       }

def main():
    logging.info(f"## Computing phenomenon dataframes")
    dict_dfs = compute_phenomenon_dataframes()
    logging.info("## Uploading phenomenon dataframes...")
    for key, value in dict_dfs.items():
        logging.info(f"Uploading dataframe '{key}'...")
        put_dataframe(value, key, type="parquet", path = PATH_AIXPA_INDEX_DFS)
        logging.info(f"Logging dataframe '{key}'...")
        log_dataframe(value, key, type="parquet")
    logging.info("## Saved.")

def local():
    """Saves locally the results"""
    logging.info("## Computing phenomenon dataframes...")
    dict_dfs = compute_phenomenon_dataframes()
    logging.info("## Saving phenomenon dataframes...")
    for key, value in dict_dfs.items():
        logging.info(f"Saving dataframe '{key}' to path...")
        put_dataframe(value, key, type="parquet", path = PATH_AIXPA_INDEX_DFS)
    logging.info(f"## Phenomena saved in the following path: {PATH_AIXPA_INDEX_DFS}.")

if __name__ == "__main__":
    local()