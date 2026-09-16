"""
Computes the "phenomenon" dataframes for flussi and arrivi, starting from
the already-standardized dataframes produced by standardize_other_raw_data.

This module owns only the DISAGGREGATION + final AGGREGATION step:
standardization (rename, merge, Vigo/Pozza unification, filtering) is done
upstream in data_preparation.v2.standardize_other_raw_data.
"""

import logging
import pandas as pd

from utils.flows_utils.main_generate_flows_and_grids import (
    main_generate_flows_and_grids,
)
from data_preparation.v2.utils.utils import (
    pad_id_comune,
    save_computed_dfs,
    get_mapping,
)
from data_preparation.v2.utils.disaggregation import disaggregate
from data_preparation.v2.standardize_other_raw_data import (
    standardize_other_raw_data,
    FLUSSI_VALUE_COLS,
    FLUSSI_LEVEL_COLS,
)
from standardize_raw_data import standardize_mapping
logging.basicConfig(level=logging.INFO)


## COMPUTATION
## Disaggregation / final aggregation only — inputs are already standardized
def compute_arrivi_trentino(arrivi_std, mapping_comuni, how="uniform", distribution=None):
    """Disaggrega arrivi da Anno/APT -> Giorno/Comune.z

    `arrivi_std` è il df già standardizzato (DATA/LOCATION/ID_COMUNE + 'arrivi'),
    prodotto da standardize_arrivi(). `mapping_comuni` qui è la mappatura
    ISTAT comune<->id completa (non quella APT usata per la standardizzazione),
    necessaria per risolvere gli ID_COMUNE aggregati durante la disaggregazione.
    """
    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    kwargs = dict(axis="both", freq_from="Y", freq_to="D", id_to_name=id_to_comune)
    if how == "distributional":
        assert distribution is not None, "Distribution required for 'distributional' disaggregation"
        kwargs.update(
            space_weights=distribution,
            space_weight_col="presenze",
            space_time_freq="Y",
            time_weights=distribution,
            time_weight_col="presenze",
        )
    elif how != "uniform":
        raise ValueError(
            f"Unknown disaggregation method: {how}, choose one between 'uniform' and 'distributional'"
        )

    arrivi = disaggregate(arrivi_std, cols=["arrivi"], **kwargs)
    arrivi["ID_COMUNE"] = pad_id_comune(arrivi["ID_COMUNE"])
    arrivi["DATA"] = pd.to_datetime(arrivi["DATA"]).dt.strftime("%Y-%m-%d")
    return arrivi


def compute_flussi_trentino(flussi_df, mapping_comuni):
    """Disaggregates flows. flussi_df is the standardized dataframe (DATA/LOCATION/ID_COMUNE
    + FLUSSI_VALUE_COLS + FLUSSI_LEVEL_COLS), produced from standardize_other_raw_data(). 

    NOTE: spatial disaggregation is applied just to FLUSSI_VALUE_COLS, not to FLUSSI_LEVEL_COLS (hotspot levels): where median is used for aggregation 
    """
    id_to_name = {id_comune: name for name, id_comune in mapping_comuni.items()}

    df = disaggregate(
        flussi_df,
        cols=FLUSSI_VALUE_COLS,
        axis="space",
        group_col="LOCATION",
        id_to_name=id_to_name,
    )

    agg_dict = {
        **{col: "sum" for col in FLUSSI_VALUE_COLS},
        **{col: "median" for col in FLUSSI_LEVEL_COLS},
    }
    df = df.groupby(["DATA", "ID_COMUNE", "LOCATION"]).agg(agg_dict).reset_index()
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return df


def compute_flussi_2023_temp(flussi_df):
    """Compute a temporary version of the flussi dataframe for 2023, using the 2024 data as a proxy.
    NOTE: IMPORTANT: This is a temporary solution, and should be replaced with actual data when available.
    """
    flussi_temp_2023 = flussi_df.copy()
    flussi_temp_2023["DATA"] = 2023
    return flussi_temp_2023


## MAIN computation of phenomena
def compute_phenomenon_dataframes(local=False):
    """Loads, standardizes and computes the "phenomenon" dataframes.

    Returns a dict with keys:
    "arrivi_trentino", "phen_flussi", "phen_flussi_temp_2023".
    Each value is a dataframe standardized to DATA/LOCATION (+ ID, + the
    phenomenon's own value columns). Any ID_COMUNE column is zero-padded to
    6 digits (e.g. 22001 -> "022001").
    """
    logging.info("Diffusion preprocessing step")
    main_generate_flows_and_grids(local=local)

    logging.info("## Standardizing raw data...")
    arrivi_std, flussi_std = standardize_other_raw_data()

    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_comuni = standardize_mapping(mapping_comuni)
    logging.info("## Computing phenomenon dataframes...")

    arrivi_trentino = compute_arrivi_trentino(arrivi_std, mapping_comuni)
    flussi_df = compute_flussi_trentino(flussi_std, mapping_comuni)
    phen_flussi_temp_2023 = compute_flussi_2023_temp(flussi_df)

    dict_dfs = {
        "phen_arrivi": arrivi_trentino,
        "phen_flussi": flussi_df,
        "phen_flussi_temp_2023": phen_flussi_temp_2023,
    }

    save_computed_dfs(dict_dfs, local=local)


if __name__ == "__main__":
    compute_phenomenon_dataframes(local=False)
