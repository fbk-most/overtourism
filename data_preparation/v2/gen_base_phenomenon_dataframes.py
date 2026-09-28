# SPDX-License-Identifier: Apache-2.0
"""
STEP 3 - Final phenomenon dataframes.

Input : Output/data_processed/
Output: Output/final_data/   (phen_popolazione, phen_strutture, phen_presenze)
        or upload to the platform 

Each phenomenon dataframe is typically contains:
  - DATA: YYYY for yearly data, YYYY-MM-DD for daily data
  - ID_COMUNE: zero-padded ISTAT code (e.g. 22001 -> "022001")
plus the phenomenon's value columns

Relevant for the indicators:
  "tasso-ricettivita", "indice-turisticita", "indice-stagionalita",
  "indice-ospitalita", "indice-turismo-sommerso"
"""
import logging
from pathlib import Path
from data_preparation.v2.utils.utils import save_computed_dfs
from data_preparation.v2.utils.disaggregation import disaggregate
from data_preparation.v2.utils.common import (
    PROCESSED_DIR, FINAL_DIR, read_df, check_output_dir,
)

logging.basicConfig(level=logging.INFO)

## COMPUTATION
## Functions to compute phenomena dataframes
## NOTE: ID_COMUNE is expected in scalar form or tuple: this logic wwas moved in read_df with parse_ids=True 
def compute_presenze_trentino(
    df_alb,
    df_extralb,
    vodafone_distribution,
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
    kwargs = dict(axis="both", freq_from="M", freq_to="D") # no id_to_name since LOCATION no more in df

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
    presenze = disaggregate(df_alb, cols=["presenze_alb"], **_weighted_kwargs(alb_col))
    presenze_prov = disaggregate(df_extralb, cols=["presenze_xalb"], **_weighted_kwargs(xalb_col))

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
    return df.sort_values(by=["DATA", "ID_COMUNE"]).reset_index(drop=True)


def compute_vodafone_attendences(
    df, how="uniform", distribution=None,
    weight_col="popolazione", weight_freq="Y",
):
    """Daily x comune vodafone tourist-presence dataframe."""
    # Aggregate daily presences by municipality
    df = (
        df.groupby(["DATA", "ID_COMUNE"])
        .agg({"presenze": "sum"})
        .reset_index()
    )
    kwargs = dict(axis="space")  # spatial disaggregation only, data is already daily
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

    return disaggregate(df, cols=["presenze"], **kwargs)


def calculate_phenomena(popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb):
    """Builds the final phenomenon dataframes from the processed ones.

    Returns a dict with keys "phen_popolazione", "phen_strutture", "phen_presenze".
    """
    ### ---------------------------------- ###
    ## 1. DISAGGREGAZIONE UNIFORME :
    ## Le presenze vodafone sono distribuite uniformemente sui comuni
    ## Le presenze ISPAT alberghiere e extra-alberghiere sono distribuite uniformemente sui comuni
    logging.info("## Computing vodafone phenomenon dataframe")
    vodafone_attendences_df = compute_vodafone_attendences(vodafone_df, how="uniform")
    logging.info("## Computing presences phenomenon dataframe")
    presenze_df = compute_presenze_trentino(presenze_df_alb, presenze_df_extralb, vodafone_attendences_df)

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

    return {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_df,
        "phen_presenze": presenze_df,
    }


## STEP computation of phenomena 
def compute_phenomenon_dataframes(processed_dir=PROCESSED_DIR, out_dir=FINAL_DIR, type_format="csv", local=True):
    """Main orchestrator, 
    local defines if to upload the phenomena or save them locally in out_dir,
    local=False uploads the phenomena to the platform """

    processed_dir = Path(processed_dir)
    check_output_dir(out_dir)

    logging.info("Reading processed data from %s", processed_dir)
    read = lambda name: read_df(processed_dir, name, type_format, parse_ids=True)
    popolazione_df = read("popolazione_pr")
    strutture_df = read("strutture_pr")
    vodafone_df = read("vodafone_pr")
    presenze_df_alb = read("presenze_alb_pr")
    presenze_df_extralb = read("presenze_extralb_pr")

    logging.info("## Computing phenomenon dataframes")
    dict_dfs = calculate_phenomena(
        popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb
    )

    logging.info("## Saving phenomenon dataframes...")
    save_computed_dfs(
            dict_dfs,
            local=local,
            type_format=type_format,
            path_saving=out_dir,
    )
    return dict_dfs


if __name__ == "__main__":
    logging.info("Step 3: Output/data_processed -> Output/final_data")
    processed_dir = PROCESSED_DIR
    out_dir = FINAL_DIR
    type_format="csv"
    upload = False
    compute_phenomenon_dataframes(
        processed_dir, out_dir, type_format, upload
    )
