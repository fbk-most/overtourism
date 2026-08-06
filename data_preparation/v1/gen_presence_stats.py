# SPDX-License-Identifier: Apache-2.0
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from data_preparation.utils import get_dataframe, put_dataframe, log_dataframe


def fit_gaussian_mixture_model(raw_df, nr_clusters=4):
    def apply_standardization(raw_df):
        scaler = StandardScaler()
        scaled_df = scaler.fit_transform(raw_df)
        scaled_df = pd.DataFrame(scaled_df)
        scaled_df.columns = raw_df.columns
        return scaled_df

    def extract_seasons_stats(
        clusters, predictions, real_observations, feature_t, feature_e
    ):
        statistics = []
        for curr_cluster in clusters.itertuples():
            cluster_name = curr_cluster.Index
            cluster_weight = curr_cluster.weight
            cluster = np.where(predictions == cluster_name)[0]
            mean_t, std_t = (
                real_observations.iloc[cluster][feature_t].mean(),
                real_observations.iloc[cluster][feature_t].std(),
            )
            mean_e, std_e = (
                real_observations.iloc[cluster][feature_e].mean(),
                real_observations.iloc[cluster][feature_e].std(),
            )
            statistics.append(
                {
                    "cluster_name": cluster_name,
                    "freq_rel": cluster_weight,
                    "mean_tourists": mean_t,
                    "std_tourists": std_t,
                    "mean_excursionists": mean_e,
                    "std_excursionists": std_e,
                }
            )
        sorted_stat = sorted(statistics, key=lambda x: x["freq_rel"])
        for ind_cluster, clust in enumerate(sorted_stat):
            clust["freq_rel_order"] = ind_cluster
        return sorted_stat

    scaled_df = apply_standardization(raw_df)
    gmm = GaussianMixture(
        n_components=nr_clusters, warm_start=True, covariance_type="diag", max_iter=200
    ).fit(scaled_df)
    gmm_predict = gmm.predict(scaled_df)
    means = gmm.means_
    cluster_predictions = Counter(gmm_predict)
    centers = pd.DataFrame(means, columns=raw_df.columns)
    centers["size"] = [cluster_predictions[i] for i in range(nr_clusters)]
    centers["weight"] = centers["size"] / centers["size"].sum()
    statistics = extract_seasons_stats(
        centers, gmm_predict, raw_df, "presences_tourists", "presences_excursionists"
    )
    return statistics


START_DATE = "2023-06-01"
END_DATE = "2023-09-30"

LOC_ID_COMUNE_MOLVENO = "27"
LOC_TYPE_COMUNE_MOLVENO = "TN_MKT_AL_3"
COMUNE_NAME = "MOLVENO"

vodafone_presences_df = get_dataframe("vodafone_attendences")

presences_df = vodafone_presences_df[
    (vodafone_presences_df["date"] >= START_DATE)
    & (vodafone_presences_df["date"] <= END_DATE)
    & (vodafone_presences_df["value"] != 0)
    & (vodafone_presences_df["userProfile"] != "INHABITANT")
    & (vodafone_presences_df["userProfile"] != "COMMUTER")
    & (vodafone_presences_df["locId"] == LOC_ID_COMUNE_MOLVENO)
    & (vodafone_presences_df["locType"] == LOC_TYPE_COMUNE_MOLVENO)
]
presences_df = presences_df[["date", "userProfile", "value", "locId"]]

# tourists
tourist_presences_df = (
    presences_df[presences_df["userProfile"] == "TOURIST"][["date", "value", "locId"]]
    .groupby(["locId", "date"])
    .sum()
    .reset_index()
)
tourist_presences_df.rename(columns={"value": "presences_tourists"}, inplace=True)

# excursionists
excursionist_presences_df = (
    presences_df[presences_df["userProfile"] == "VISITOR"][["date", "value", "locId"]]
    .groupby(["locId", "date"])
    .sum()
    .reset_index()
)
excursionist_presences_df.rename(
    columns={"value": "presences_excursionists"}, inplace=True
)

# all
presences_df = pd.merge(
    tourist_presences_df, excursionist_presences_df, how="inner", on=["date", "locId"]
)[["presences_tourists", "presences_excursionists"]]

# fit gaussian mixture model
season = fit_gaussian_mixture_model(presences_df, nr_clusters=3)

# prepare the output dataframe
season_df = (
    pd.DataFrame(season)
    .drop(columns="cluster_name")
    .sort_values(by=["mean_tourists"])
    .set_index([pd.Index(["low", "mid", "high"], name="cluster_name")])
)


weather_stats = pd.DataFrame(
    [
        [0.15, 140.30952381, 463.13601314, -773.23809524, 1187.05786413],
        [0.20, 128.32142857, 319.20470369, 31.10714286, 824.51775728],
        [0.65, 72.86263736, 406.09163233, 282.91208791, 839.91419686],
    ],
    columns=[
        "freq_rel",
        "mean_tourists",
        "std_tourists",
        "mean_excursionists",
        "std_excursionists",
    ],
    index=["bad", "unsettled", "good"],
)

weekday_stats = pd.DataFrame(
    [
        [-362.65934066, 112.47000414, -391.15384615, 791.84158997],
        [-265.34065934, 122.13648742, -352.27472527, 937.65181712],
        [-147.92307692, 247.5534754, -465.62637363, 733.9652083],
        [92.23076923, 233.81638923, -380.35164835, 779.58869239],
        [678.05494505, 149.44551186, -232.91208791, 500.50732948],
        [320.46938776, 204.41996226, 590.98979592, 797.28902804],
        [-278.93406593, 193.01797188, 1240.27472527, 1149.59709071],
    ],
    columns=[
        "mean_tourists",
        "std_tourists",
        "mean_excursionists",
        "std_excursionists",
    ],
    index=[
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ],
)


def main():
    # save the output
    log_dataframe(season_df, "season_stats_ot")
    log_dataframe(weather_stats, "weather_stats_ot")
    log_dataframe(weekday_stats, "weekday_stats_ot")


def local():
    # save the output locally
    put_dataframe(season_df, "season_stats_ot")
    put_dataframe(weather_stats, "weather_stats_ot")
    put_dataframe(weekday_stats, "weekday_stats_ot")


if __name__ == "__main__":
    # script executed locally
    local()
