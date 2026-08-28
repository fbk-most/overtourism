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

import pandas as pd
import geopandas as geopd
from data_preparation.v2.utils.utils import (
    save_computed_dfs,
    get_dataframe,
    get_s3,
    get_json_s3,
    _remove_provincia,
    _to_data_location,
    pad_id_comune,
    customize_unidecode,
    resolve_id_comune,
    get_mapping_comuni,
    COMUNE_NAME_OVERRIDES,
)
from data_preparation.v2.utils.disaggregation import disaggregate

logging.basicConfig(level=logging.INFO)

STRUTTURE_VALUE_COLS = [
    "tot_postiletto",
    "tot_postiletto_non_conv",
    "tot_postiletto_conv",
    "tot_strutture",
    "tot_strutture_non_conv",
    "tot_postiletto_alberghieri",
    "tot_postiletto_extralberghieri"
]

## COMPUTATION
## Functions to compute phenomena dataframes
def compute_presenze_trentino(
    mapping_comuni,
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
        presenze_ispat, cols=["presenze_alb"], **_weighted_kwargs(alb_col)
    )
    presenze_prov = disaggregate(
        presenze_alb_xalb, cols=["presenze_xalb"], **_weighted_kwargs(xalb_col)
    )

    # presenze_alb is kept at the finer (APT) granularity, only the
    # extra-alberghiero column is taken from the province-level estimate
    df = presenze.merge(
        presenze_prov[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"]).dt.strftime("%Y-%m-%d")
    df = df.merge(
        vodafone_distribution[["DATA", "ID_COMUNE", "presenze"]].rename(columns={"presenze": "presenze_vodafone"}),
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )
    df = df.sort_values(by=["DATA", "LOCATION"]).reset_index(drop=True)
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
    """Yearly comune accommodation-capacity dataframe."""
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

    CATEGORIA_ALBERGHIERI_LETTI = "alberghieri posti_letto"
    CATEGORIA_EXTRALBERGHIERI_LETTI = "extra alb. Posti_letto"
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
    strutture_ospitalita_from_2020["tot_postiletto_alberghieri"] = (
        strutture_ospitalita_from_2020[CATEGORIA_ALBERGHIERI_LETTI]
    )
    strutture_ospitalita_from_2020["tot_postiletto_extralberghieri"] = (
        strutture_ospitalita_from_2020[CATEGORIA_EXTRALBERGHIERI_LETTI]
    )

    # conventional-only beds (tot_postiletto minus the non-conv share) 
    strutture_ospitalita_from_2020["tot_postiletto_conv"] = (
        strutture_ospitalita_from_2020[CATEGORIA_TOT_CONVENZIONALI_LETTI]
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

    result = strutture_ospitalita_from_2020[
        ["DATA", "LOCATION", "ID_COMUNE"] + STRUTTURE_VALUE_COLS
    ]
    return result


def compute_vodafone_attendences(
    mapping_comuni, how="uniform", distribution=None,
    weight_col="popolazione", weight_freq="Y",
):
    """Daily x comune vodafone tourist-presence dataframe."""
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
    else:
        assert distribution is None

    df = disaggregate(df, cols=["presenze"], **kwargs)

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
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

    mapping_comuni = get_mapping_comuni()
    popolazione_df = compute_popolazione(mapping_comuni)   # comunale, annuale

    strutture_df = compute_strutture(
        mapping_comuni
    ) # comunale, annuale (o giornaliera se strutture_to_daily=True)

    ## UNIFORM :
    # vodafone_attendences_df = compute_vodafone_attendences(mapping_comuni, how="uniform")# vodafone_attendences_df = compute_vodafone_attendences(mapping_comuni, how="uniform")
    # presenze_df = compute_presenze_trentino(mapping_comuni, vodafone_attendences_df, how="uniform")

    # VODAFONE PRESENZE, redistribuite uniformemente
    # vodafone_attendences_df = compute_vodafone_attendences(
    #         mapping_comuni
    # ) # how="distributional", distribution=popolazione_df, weight_col="popolazione", weight_freq="Y",

    # presenze_df = compute_presenze_trentino(
    #     mapping_comuni, vodafone_attendences_df, how="distributional",
    # )  # weighting_distribution defaults to vodafone_distribution itself


    ## PRESENZE 
    vodafone_attendences_df = compute_vodafone_attendences(
        mapping_comuni, how="distributional",
        distribution=strutture_df, weight_col="tot_postiletto",
        weight_freq="Y",
    )

    # presenze_df = compute_presenze_trentino(
    #         mapping_comuni, vodafone_attendences_df, how="distributional",
    #         weighting_distribution=strutture_df,
    #         alb_weight_col="tot_postiletto_alberghieri",
    #         xalb_weight_col="tot_postiletto_extralberghieri",
    #         space_weight_freq="Y",
    #         time_weight_freq="Y",
    #     )

    dict_dfs = {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_df,
        "phen_presenze": presenze_df,
    }

    logging.info("## Saving phenomenon dataframes...")
    save_computed_dfs(dict_dfs, local=local)


if __name__ == "__main__":
    compute_phenomenon_dataframes(local=True)