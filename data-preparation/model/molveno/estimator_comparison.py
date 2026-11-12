# SPDX-License-Identifier: Apache-2.0
"""
Validation of the estimators of the Molveno presence statistics (evidence of D9, ASSUMPTIONS.md).

    python -m model.molveno.estimator_comparison    # after python -m model.molveno.prepare

Leave-one-year-out on the training summers (train on two, test on the third). Each estimator
predicts, for a test day, the mean and the SD of tourists and excursionists from what a scenario
knows: the date, the weekday and the weather class. Scores: MAE, RMSE, R², CRPS of the normal
predictive distribution, coverage of the 90 % interval. Output: <analysis>/estimator_comparison_*.csv.

Estimators
* ``gbm_statistics``: the main statistics (``gbm_presence_stats``, D9-D12), looked up by
  calendar day, weekday and weather class.
* ``monthly_statistics``: the comparison statistics (``additive_presence_stats``), looked up by
  month, weekday and weather class.
* ``season_sums``: season (month) mean + weekday shift + weather shift, with the season, weekday
  and weather SDs combined as independent.
* ``gbm_class_feature``: gradient boosting with the weather class as a feature instead of the
  measured weather (D10).
* ``gbm_actual_weather``: gradient boosting with the measured weather of the test day (not
  available to a scenario: upper bound).
* ``additive_weekly``, ``tree_seasons_4``, ``tree_seasons_8``: least squares on week or on
  seasons learnt by a regression tree on the day of the summer, x weekday + weather class: the
  gain of a finer calendar alone.
* ``gbm_monthly``, ``gbm_half_monthly``: gradient boosting statistics aggregated to month or
  half-month cells.
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.tree import DecisionTreeRegressor

from model.molveno import presence_estimators as pe
from model.molveno.config import MOLVENO_DIR
from model.molveno.prepare import read_reference

logger = logging.getLogger(__name__)

ANALYSIS_DIR = MOLVENO_DIR / "data" / "analysis_output"
INTERVAL_Z = stats.norm.ppf(0.95)
SCORES = ["mae", "rmse", "r2", "crps", "coverage90", "mean_sd"]


# ------------------------------------------------------------------ estimators
def gbm_statistics(train, test, y):
    cells = pe.gbm_presence_stats(train).set_index(["month_day", "weekday", "weather"])
    keys = pd.MultiIndex.from_arrays([test["month_day"], test["weekday"].map(dict(enumerate(pe.WEEKDAYS))), test["weather"]])
    cell = cells.reindex(keys)
    return cell[f"mean_{y}"].values, cell[f"std_{y}"].values


def monthly_statistics(train, test, y):
    cells = pe.additive_presence_stats(train).set_index(["month", "weekday", "weather"])
    keys = pd.MultiIndex.from_arrays([test["month"], test["weekday"].map(dict(enumerate(pe.WEEKDAYS))), test["weather"]])
    cell = cells.reindex(keys)
    return cell[f"mean_{y}"].values, cell[f"std_{y}"].values


def season_sums(train, test, y):
    season = train.groupby("month")[y].agg(["mean", "std"])
    dev = train[y] - train["month"].map(season["mean"])
    weekday = dev.groupby(train["weekday"]).agg(["mean", "std"])
    weather = dev.groupby(train["weather"]).agg(["mean", "std"])
    mean = (test["month"].map(season["mean"]) + test["weekday"].map(weekday["mean"])
            + test["weather"].map(weather["mean"]))
    var = (test["month"].map(season["std"]) ** 2 + test["weekday"].map(weekday["std"]) ** 2
           + test["weather"].map(weather["std"]) ** 2)
    return mean.values, np.sqrt(var.values)


def _gbm_daily(features):
    def predict(train, test, y):
        x = lambda d: pd.get_dummies(d[features]).astype(float)  # noqa: E731
        columns = x(train).columns
        model, sd = pe.fit_gbm(train.assign(**x(train)), y, list(columns))
        return model.predict(x(test).reindex(columns=columns, fill_value=0.0)), np.full(len(test), sd)
    return predict


def _least_squares(train, test, y, season_train, season_test):
    def design(d, season):
        season = np.asarray(season).astype(str)
        cells = pd.DataFrame({"season_weekday": np.char.add(np.char.add(season, "_"), d["weekday"].to_numpy().astype(str)),
                              "weather": d["weather"].to_numpy()})
        return pd.get_dummies(cells).astype(float)
    xtr = design(train, season_train)
    xte = design(test, season_test).reindex(columns=xtr.columns, fill_value=0.0)
    coef, *_ = np.linalg.lstsq(xtr.values, train[y].values, rcond=None)
    resid = train[y].values - xtr.values @ coef
    return xte.values @ coef, np.full(len(test), resid.std(ddof=np.linalg.matrix_rank(xtr.values)))


def _additive_by(season_of):
    def predict(train, test, y):
        return _least_squares(train, test, y, season_of(train), season_of(test))
    return predict


def tree_seasons(train, n_seasons):
    """Regression tree on the day of the summer, both presences standardized: its leaves are seasons."""
    target = train[list(pe.PRESENCES)]
    return DecisionTreeRegressor(max_leaf_nodes=n_seasons, min_samples_leaf=20, random_state=0).fit(
        train[["summer_day"]], (target - target.mean()) / target.std())


def season_boundaries(tree, year=2025):
    cal = pe.summer_calendar(year).drop_duplicates("summer_day")
    leaves = tree.apply(cal[["summer_day"]])
    starts = [0] + [i for i in range(1, len(leaves)) if leaves[i] != leaves[i - 1]]
    ends = starts[1:] + [len(leaves)]
    days = cal["month_day"].tolist()
    return [f"{days[a]}..{days[b - 1]}" for a, b in zip(starts, ends)]


def _tree(n):
    def predict(train, test, y):
        tree = tree_seasons(train, n)
        return _least_squares(train, test, y, pd.Series(tree.apply(train[["summer_day"]])),
                              pd.Series(tree.apply(test[["summer_day"]])))
    return predict


def _gbm_aggregated(period_of):
    def predict(train, test, y):
        cells = pe.gbm_presence_stats(train)
        mean_col, std_col = f"mean_{y}", f"std_{y}"
        cells["period"] = period_of(cells)
        cells["var"] = cells[std_col] ** 2
        g = cells.groupby(["period", "weekday", "weather"])
        agg = pd.DataFrame({"mean": g[mean_col].mean(), "std": np.sqrt(g[mean_col].var(ddof=0) + g["var"].mean())})
        keys = pd.MultiIndex.from_arrays([period_of(test), test["weekday"].map(dict(enumerate(pe.WEEKDAYS))), test["weather"]])
        cell = agg.reindex(keys)
        return cell["mean"].values, cell["std"].values
    return predict


def _week(d):
    return (d["summer_day"] // 7).to_numpy().astype(str)


def _month(d):
    return d["month"].to_numpy().astype(str)


def _half_month(d):
    half = np.where(d["month_day"].str[3:].astype(int).to_numpy() <= 15, "a", "b")
    return np.char.add(_month(d), half)


ESTIMATORS = {
    "gbm_statistics": gbm_statistics,
    "monthly_statistics": monthly_statistics,
    "season_sums": season_sums,
    "gbm_class_feature": _gbm_daily(pe.CALENDAR_FEATURES + ["weather"]),
    "gbm_actual_weather": _gbm_daily(pe.GBM_FEATURES),
    "additive_weekly": _additive_by(_week),
    "tree_seasons_4": _tree(4),
    "tree_seasons_8": _tree(8),
    "gbm_monthly": _gbm_aggregated(_month),
    "gbm_half_monthly": _gbm_aggregated(_half_month),
}


# ------------------------------------------------------------------ scores
def crps_normal(y, mean, sd):
    z = (y - mean) / sd
    return sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))


def scores(y, mean, sd) -> dict[str, float]:
    err = y - mean
    return {
        "mae": np.abs(err).mean(),
        "rmse": np.sqrt((err ** 2).mean()),
        "r2": 1 - (err ** 2).sum() / ((y - y.mean()) ** 2).sum(),
        "crps": crps_normal(y, mean, sd).mean(),
        "coverage90": (np.abs(err) <= INTERVAL_Z * sd).mean(),
        "mean_sd": sd.mean(),
    }


def compare(daily: pd.DataFrame, estimators=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leave-one-year-out scores per estimator, presence and test year; and the tree seasons.
    Weather classes use the climatology of the training years only."""
    estimators = estimators or ESTIMATORS
    days = pe.training_days(daily)
    meteo = days[["date", "tmax"]]
    rows, seasons = [], []
    for year in pe.TRAINING_YEARS:
        clim = pe.weather_climatology(meteo[days["year"] != year], [y for y in pe.TRAINING_YEARS if y != year])
        d = pe.add_weather(days, clim)
        train, test = d[d["year"] != year].reset_index(drop=True), d[d["year"] == year].reset_index(drop=True)
        seasons.append({"test_year": year, **{f"tree_seasons_{n}": " | ".join(season_boundaries(tree_seasons(train, n)))
                                              for n in (4, 8)}})
        for y in pe.PRESENCES:
            for name, predict in estimators.items():
                mean, sd = predict(train, test, y)
                rows.append({"estimator": name, "presence": y, "test_year": year,
                             **scores(test[y].values, np.asarray(mean, float), np.asarray(sd, float))})
    return pd.DataFrame(rows), pd.DataFrame(seasons)


def main():
    logging.basicConfig(level=logging.INFO)
    detail, seasons = compare(read_reference()["molveno_daily"])
    summary = detail.groupby(["presence", "estimator"], sort=False)[SCORES].mean()
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(ANALYSIS_DIR / "estimator_comparison_detail.csv", index=False)
    summary.to_csv(ANALYSIS_DIR / "estimator_comparison_summary.csv")
    seasons.to_csv(ANALYSIS_DIR / "estimator_comparison_tree_seasons.csv", index=False)
    with pd.option_context("display.float_format", "{:.2f}".format, "display.width", 160, "display.max_columns", 20):
        print(summary)
        print(seasons.T.to_string(header=False))


if __name__ == "__main__":
    main()
