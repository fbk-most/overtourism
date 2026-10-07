# SPDX-License-Identifier: Apache-2.0
"""Computation of the final phenomenon dataframes from the processed ones (pure functions)."""

import logging

logger = logging.getLogger(__name__)


def compute_presenze_trentino(df_alb, df_extralb, df_vodafone):
    """Daily x comune presences dataframe: ISPAT alb + xalb and vodafone presences."""
    df = df_alb.merge(
        df_extralb[["DATA", "ID_COMUNE", "presenze_xalb"]],
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )

    len_pre = len(df)
    df_mg = df.merge(
        df_vodafone[["DATA", "ID_COMUNE", "presenze"]].rename(
            columns={"presenze": "presenze_vodafone"}
        ),
        on=["DATA", "ID_COMUNE"],
        how="inner",
    )

    if len(df_mg) < len_pre:
        records_lost = len_pre - len(df_mg)
        perc_lost = (records_lost / len_pre) * 100
        missing_dates = set(df["DATA"].dropna()) - set(df_vodafone["DATA"].dropna())

        rows_missing_dates = int(df["DATA"].isin(missing_dates).sum())
        rows_missing_keys = records_lost - rows_missing_dates

        logger.warning(
            "Filtered Vodafone: %d/%d records discarded (%.2f%%).",
            records_lost,
            len_pre,
            perc_lost,
        )
        if missing_dates:
            min_d, max_d = min(missing_dates), max(missing_dates)
            logger.warning(
                "Records lost on dates not covered by Vodafone: %d records across %d days (%s..%s).",
                rows_missing_dates,
                len(missing_dates),
                min_d,
                max_d,
            )
            logger.warning("First day missing: %s | Last: %s", min_d, max_d)
        if rows_missing_keys:
            logger.warning(
                "%d Records lost because of missing ID_COMUNE on common dates.",
                rows_missing_keys,
            )
    return df_mg.sort_values(by=["DATA", "ID_COMUNE"]).reset_index(drop=True)


def calculate_phenomena(
    popolazione_df, strutture_df, vodafone_df, presenze_df_alb, presenze_df_extralb
):
    """Builds the final phenomenon dataframes from the processed ones.
    Returns a dict with keys "phen_popolazione", "phen_strutture", "phen_presenze".
    """
    logger.info("## Computing presences phenomenon dataframe")
    presenze_df = compute_presenze_trentino(presenze_df_alb, presenze_df_extralb, vodafone_df)

    return {
        "phen_popolazione": popolazione_df,
        "phen_strutture": strutture_df,
        "phen_presenze": presenze_df,
    }
