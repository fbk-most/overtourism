import logging
import pandas as pd
from data_preparation.v2.utils.utils import (
    get_s3,
    pad_id_comune,
    get_mapping
)
from standardize_raw_data import _standardize

logging.basicConfig(level=logging.INFO)

FLUSSI_EXTRA_MAPPING = {
    "BENESELLO + CALLIANO + VOLANO": "BESENELLO + CALLIANO + VOLANO",
    "BORGO CHIESE + CASTEL CONDINO + PIEVE DI BONO-PREZ": "BORGO CHIESE + CASTEL CONDINO + PIEVE DI BONO-PREZZO",
    "PERGINE VALSUGANA + VIGNOLA-FALESINA (NORD)": "PERGINE VALSUGANA + VIGNOLA-FALESINA",
    "PERGINE VALSUGANA + VIGNOLA-FALESINA (SUD)": "PERGINE VALSUGANA + VIGNOLA-FALESINA",
    "RIVA DEL GARDA (PAESE)": "RIVA DEL GARDA",
    "RIVA DEL GARDA (SUL LAGO)": "RIVA DEL GARDA",
    "ROVERETO (BORGO SACCO)": "ROVERETO",
    "ROVERETO (CENTRO)": "ROVERETO",
    "ROVERETO (LIZZANA - OSPEDALE)": "ROVERETO",
    "ROVERETO (MARCO)": "ROVERETO",
    "ROVERETO (NORIGLIO)": "ROVERETO",
    "SANT'ORSOLA TERME + FRASSILONGO + PALU' DEL FERSIN": "SANT'ORSOLA TERME + FRASSILONGO + PALU' DEL FERSINA",
    "TN CENTRO": "TRENTO",
    "TN EST": "TRENTO",
    "TN NORD": "TRENTO",
    "TN OLTRE ADIGE NORD": "TRENTO",
    "TN OLTRE ADIGE SUD": "TRENTO",
    "TN SUD": "TRENTO",
}

df__map = {
        "AREA_ID": "ID",
        "AREA_LABEL": "comune",
        "tot_in_flows_t_0_0_w_all_days_d_": "FLOWS_IN",
        "tot_out_flows_t_0_0_w_all_days_d_": "FLOWS_OUT",
        "hotspot_level_tot_in_flows_t_0_0_w_all_days_d_": "LEVEL_IN",
        "hotspot_level_tot_out_flows_t_0_0_w_all_days_d_": "LEVEL_OUT",
    }

df_u_map = {
        "AREA_ID": "ID",
        "AREA_LABEL": "comune",
        "hotspot_level_tot_in_flows_TOURIST_t_0_0_w_all_days_d_": "LEVEL_IN_TOURISTS",
        "tot_in_flows_TOURIST_t_0_0_w_all_days_d_": "FLOWS_IN_TOURISTS",
        "hotspot_level_tot_out_flows_TOURIST_t_0_0_w_all_days_d_": "LEVEL_OUT_TOURISTS",
        "tot_out_flows_TOURIST_t_0_0_w_all_days_d_": "FLOWS_OUT_TOURISTS",
        "hotspot_level_tot_in_flows_VISITOR_t_0_0_w_all_days_d_": "LEVEL_IN_VISITORS",
        "tot_in_flows_VISITOR_t_0_0_w_all_days_d_": "FLOWS_IN_VISITORS",
        "hotspot_level_tot_out_flows_VISITOR_t_0_0_w_all_days_d_": "LEVEL_OUT_VISITORS",
        "tot_out_flows_VISITOR_t_0_0_w_all_days_d_": "FLOWS_OUT_VISITORS",
    }

FLUSSI_VALUE_COLS = [
    "FLOWS_IN",
    "FLOWS_OUT",
    "FLOWS_IN_TOURISTS",
    "FLOWS_OUT_TOURISTS",
    "FLOWS_IN_VISITORS",
    "FLOWS_OUT_VISITORS",
]

FLUSSI_LEVEL_COLS = [
    "LEVEL_IN",
    "LEVEL_OUT",
    "LEVEL_IN_TOURISTS",
    "LEVEL_OUT_TOURISTS",
    "LEVEL_IN_VISITORS",
    "LEVEL_OUT_VISITORS",
]

## HELPER FUNCTIONS for standardization

def _pre_filtering_flussi(df, colmap):
    """Pre-filterin: selection of Trentino area"""
    df = df[list(colmap)]
    return df[df["AREA_ID"].str.startswith("ITA.04.022.", na=False)].copy()


def standardize_arrivi(df, mapping_comuni, years=["2021", "2022", "2023", "2024"]):
    """Leads arrivi df to a standard format"""
    df = df.rename(columns={"Anno": "anno", "Ambito": "comune"})
    df = pd.melt(df, id_vars="comune", value_vars=years, value_name="arrivi", var_name="anno")
    df["anno"] = df["anno"].astype(int)
    df["ID_COMUNE"] = df["comune"].map(mapping_comuni).apply(
        lambda x: [int(i) for i in x] if isinstance(x, list) else x
    )
    return _standardize(df, date_col="anno", df_name = "arrivi_df")


def _standardize_flussi_component(df, colmap, year):
    """Leads flows df to a standard format"""
    df = df.rename(columns=colmap)
    df["comune"] = df["comune"].str.upper().str.strip()
    df["anno"] = year
    return _standardize(df, date_col="anno", remove_provincia=False, df_name = "flussi_df")


def standardize_flussi_all(df_all, year=2024):
    """Flows df (all) standardization"""
    return _standardize_flussi_component(df_all, df__map, year)


def standardize_flussi_user(df_user, year=2024):
    """Flows df (users) standardization"""
    return _standardize_flussi_component(df_user, df_u_map, year)


def _flussi_id_map(df_user, mapping_comuni):
    names = df_user["LOCATION"].str.upper().str.strip()
    ids = names.map(mapping_comuni)

    unmapped = ids.isna()
    ids[unmapped] = names[unmapped].map(FLUSSI_EXTRA_MAPPING).map(mapping_comuni)

    for idx in ids.index[names.isin(["VIGO DI FASSA", "POZZA DI FASSA"])]:
        ids.at[idx] = [22250]
    return dict(zip(df_user["ID"], ids))


def combine_flussi(df_all, df_user, mapping_comuni):
    """Performs merge of flows dfs"""
    df_all = df_all.copy()
    df_all[["FLOWS_IN", "FLOWS_OUT"]] *= 4

    df_merged = pd.merge(
        df_all, df_user, on=["ID", "LOCATION", "DATA"], how="outer", indicator=True
    )
    unmatched = (df_merged["_merge"] != "both").sum()
    if unmatched > 0:
        logging.warning(f"WARNING: discrepancies found in IDs: {unmatched}")
    df_merged = df_merged.drop(columns=["_merge"])

    df_merged["ID_COMUNE"] = df_merged["ID"].map(_flussi_id_map(df_user, mapping_comuni))
    df_merged["ID_COMUNE"] = pad_id_comune(df_merged["ID_COMUNE"])  
    return df_merged


def _post_filtering_flussi(df):
    """Post-filtering: selection of columns of interest"""
    keep_cols = ["ID", "DATA", "LOCATION", "ID_COMUNE"] + FLUSSI_VALUE_COLS + FLUSSI_LEVEL_COLS
    return df[keep_cols].copy()

def standardize_other_raw_data():    
    """Leading raw data to a standardized format"""
    mapping_vodafone = get_mapping("mapping_comuni_into_vodafone_Trento.json")
    mapping_apt = get_mapping("map_comuni_into_apt.json")

    arrivi_df = pd.read_csv(get_s3("arrivi_trentino_ISPAT.csv"))
    df_all_flows = _pre_filtering_flussi(pd.read_parquet(get_s3("grid_all_columns__.parquet")), df__map)
    df_users_flows = _pre_filtering_flussi(pd.read_parquet(get_s3("grid_all_columns_user.parquet")), df_u_map)

    arrivi_df = standardize_arrivi(arrivi_df, mapping_apt)
    df_all = standardize_flussi_all(df_all_flows)
    df_user = standardize_flussi_user(df_users_flows)

    df_flussi = _post_filtering_flussi(combine_flussi(df_all, df_user, mapping_vodafone))
    return arrivi_df, df_flussi


if __name__ == "__main__":
    standardize_other_raw_data()