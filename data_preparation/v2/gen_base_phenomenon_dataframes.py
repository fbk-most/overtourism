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
import logging
from data_preparation.v2.utils.utils import (
    save_computed_dfs,
    get_mapping
)
from data_preparation.v2.standardize_raw_data import standardize_base_raw_data, standardize_mapping
from data_preparation.v2.utils.disaggregation import disaggregate

logging.basicConfig(level=logging.INFO)


## COMPUTATION
## Functions to compute phenomena dataframes
def compute_presenze_trentino(
    df_alb,
    df_extralb,
    vodafone_distribution,
    mapping_comuni,
    how="uniform",
    weighting_distribution=None,
    weight_col=None,
    alb_weight_col=None,
    xalb_weight_col=None,
    space_weight_freq="M",
    time_weight_freq=None,
):
    """Build the daily x comune ISPAT presenze dataframe (alb + xalb).

    `weighting_distribution` / `weight_col` control *what* weights the
    'distributional' disaggregation of the ISPAT presences:
      - left as None (default): `vodafone_distribution` with
        weight_col="presenze" — the original behaviour.
      - pass e.g. a daily-disaggregated structures dataframe (see
        `compute_strutture with weight_col="tot_postiletto" to weight by accommodation
        instead of vodafone presences.

    `space_weight_freq` / `time_weight_freq` control the granularity at
    which the weighting distribution's DATA is compared against the ISPAT
    row's DATA during, respectively, the comune-split step (still
    monthly at that point) and the day-of-month split step (already daily
    at that point). Defaults reproduce the original vodafone-weighted
    behaviour (monthly match spatially, exact-date match temporally).
    """

    ## Monthly x APT -> daily x comune
    id_to_comune = {id_comune: name for name, id_comune in mapping_comuni.items()}
    kwargs = dict(axis="both", freq_from="M", freq_to="D", id_to_name=id_to_comune)

    def _weighted_kwargs(col):
        if how != "distributional":
            return dict(kwargs)
        source = weighting_distribution if weighting_distribution is not None else vodafone_distribution
        assert source is not None, "A weighting distribution is required for 'distributional' disaggregation"
        return dict(
            kwargs,
            space_weights=source,
            space_weight_col=col,
            space_time_freq=space_weight_freq,
            time_weights=source,
            time_weight_col=col,
            time_weight_freq=time_weight_freq,
        )

    if how not in ("distributional", "uniform"):
        raise ValueError(f"Unknown disaggregation method: {how}")

    default_col = weight_col if weight_col is not None else "presenze"
    alb_col = alb_weight_col if alb_weight_col is not None else default_col
    xalb_col = xalb_weight_col if xalb_weight_col is not None else default_col

    # own _W column via its own disaggregate() call, since a single call applies one shared weight to every column passed in `cols`.
    presenze = disaggregate(
        df_alb, cols=["presenze_alb"], **_weighted_kwargs(alb_col)
    )
    presenze_prov = disaggregate(
        df_extralb, cols=["presenze_xalb"], **_weighted_kwargs(xalb_col)
    )

    # presenze_alb is kept at the finer (APT) granularity, only the
    # extra-alberghiero column is taken from the province-level estimate
    df = presenze.merge(
        presenze_prov[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    df = df.merge(
        vodafone_distribution[["DATA", "ID_COMUNE", "presenze"]].rename(columns={"presenze": "presenze_vodafone"}),
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    df = df.sort_values(by=["DATA", "LOCATION"]).reset_index(drop=True)
    return df



def compute_vodafone_attendences(
    df, mapping_comuni, how="uniform", distribution=None,
    weight_col="popolazione", weight_freq="Y",
):
    """Daily x comune vodafone tourist-presence dataframe."""
    # Aggregate daily presences by municipality
    df = (
        df.groupby(["DATA", "LOCATION"])
        .agg({"ID_COMUNE": "first", "presenze": "sum"})
        .reset_index()
    )
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
    else:
        assert distribution is None

    df = disaggregate(df, cols=["presenze"], **kwargs)
    return df

## MAIN computation of phenomena 
def compute_phenomenon_dataframes(local=False):
    """Loads and prepares the base "phenomenon" dataframes.

    Returns a dict with keys:
      "phen_strutture_ospitalita", "phen_popolazione",
      "phen_vodafone_attendences", "phen_arrivi_trentino"
    Each value is a dataframe standardized to DATA/LOCATION (+ ID, + the
    phenomenon's own value columns). Any ID_COMUNE column is zero-padded to
    6 digits (e.g. 22001 -> "022001").

    This functions is used to generate base phenomeon that are
    relevant for the following indicators
    - "tasso-ricettivita"
    - "indice-turisticita"
    - "indice-stagionalita"
    - "indice-ospitalita"
    - "indice-turismo-sommerso"
    """
    
    logging.info(f"## Computing phenomenon dataframes")
    logging.info("STANDARDIZATION OF RAW DATA...")
    popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb = standardize_base_raw_data()
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json")
    mapping_comuni = standardize_mapping(mapping_comuni)

    logging.info("COMPUTATION OF PHENOMENA...")
    ## strutture and popolazione: all yet done (corresponds to the standardized version)    

    ### ---------------------------------- ### 
    ## 1. DISAGGREGAZIONE UNIFORME :
    ## Le presenze vodafone sono distribuite uniformemente sui comuni
    ## Le presenze ISPAT alberghiere e Le presenze ISPAT extra-alberghiere sono distribuite uniformemente sui comuni
    vodafone_attendences_df = compute_vodafone_attendences(vodafone_df, mapping_comuni, how="uniform")
    presenze_df = compute_presenze_trentino(presenze_df_alb, presenze_df_extralb, vodafone_attendences_df, mapping_comuni)

    ### -------------------------------------------------------------------- ### 
    # 2. VODAFONE PRESENZE
    ## Le presenze vodafone sono distribuite uniformemente sui comuni
    ## Le presenze ISPAT alberghiere e Le presenze ISPAT extra-alberghiere sono distribuite seguendo la distribuzione vodafone giornaliera
    # vodafone_attendences_df = compute_vodafone_attendences(
    #         mapping_comuni
    # )

    # presenze_df = compute_presenze_trentino(
    #     mapping_comuni, vodafone_attendences_df, how="distributional",
    # )  # weighting_distribution defaults to vodafone_distribution itself


    ### -------------------------------------------------------------------- ### 
    # 3. DISAGGREGAZIONE DISTRIBUZIONALE, WRT POSTI LETTO  
    ## Le presenze vodafone sono distribuite seguendo la distribuzione annuale dei posti letto totali, sui comuni
    # Le presenze ISPAT alberghiere e Le presenze ISPAT extra-alberghiere sono distribuite seguendo rispettivamente le distribuzioni dei posti letto alberghieri ed extra-alberghieri

    # vodafone_attendences_df = compute_vodafone_attendences(
    #     mapping_comuni, how="distributional",
    #     distribution=strutture_df, weight_col="tot_postiletto",
    #     weight_freq="Y",
    # ) # distribution=popolazione_df, weight_col="popolazione", weight_freq="Y", se si volesse per esempio distribuire rispetto alla popolazione 

    # presenze_df = compute_presenze_trentino(
    #         mapping_comuni, vodafone_attendences_df, how="distributional",
    #         weighting_distribution=strutture_df,
    #         alb_weight_col="tot_postiletto_alberghieri",
    #         xalb_weight_col="tot_postiletto_extralberghieri",
    #         space_weight_freq="Y",
    #         time_weight_freq="Y",
    #     )

    ### -------------------------------------------------------------------- ### 

    dict_dfs = {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_df,
        "phen_presenze": presenze_df,
    }

    logging.info("## Saving phenomenon dataframes...")
    save_computed_dfs(dict_dfs, local=local)


if __name__ == "__main__":
    compute_phenomenon_dataframes(local=False)