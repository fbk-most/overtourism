# SPDX-License-Identifier: Apache-2.0
"""
Estimators of the Molveno presence statistics (IDs refer to ASSUMPTIONS.md).

* Main (D9): gradient boosting per summer day on the calendar (day of the summer, weekday,
  public holiday) and the measured weather (tmax anomaly, rain). Exported per calendar day x
  weekday x weather class: a class stands for the weather days of that class observed in the
  month (D10, A4), so the mean and SD are taken over the predictions with each of them, the SD
  combined with the residual SD (D12).
* Comparison (D9): least squares on month x weekday + weather class, residual SD; exported per
  month x weekday x weather class.

Both are trained on the pooled summers (D7) and return normal predictive distributions (D12).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

PRESENCES = ("tourists", "excursionists")
SUMMER = ("06-01", "09-30")  # D7: the model's period
TRAINING_YEARS = (2023, 2024, 2025)  # D7: complete summers of Vodafone and weather
HOLIDAYS = ("06-02", "08-15")  # A2: public holidays of the summer (Festa della Repubblica, Ferragosto)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
WEATHER_CLASSES = ("good", "cool", "rainy")
RAINY_MM = 5.0  # A1: rainy day = rain >= 5 mm
COOL_DEGREES = 2.0  # A1: cool day = not rainy, tmax below the month's climatological mean - 2 C
CALENDAR_FEATURES = ["summer_day", "weekday", "holiday"]
WEATHER_FEATURES = ["tmax_anomaly", "rain_mm"]
GBM_FEATURES = CALENDAR_FEATURES + WEATHER_FEATURES
GBM_PARAMS = {  # A6: fixed, not tuned
    "max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 10,
    "l2_regularization": 1.0, "random_state": 0,
}


# ------------------------------------------------------------------ features
def add_calendar(d: pd.DataFrame) -> pd.DataFrame:
    """Calendar features of the dates in ``d["date"]``; ``summer_day`` = days since 1 June (no
    leap-year shift)."""
    d = d.copy()
    date = d["date"]
    d["year"] = date.dt.year
    d["month"] = date.dt.month
    d["month_day"] = date.dt.strftime("%m-%d")
    d["summer_day"] = (date - pd.to_datetime(date.dt.year.astype(str) + "-" + SUMMER[0])).dt.days
    d["weekday"] = date.dt.dayofweek
    d["holiday"] = d["month_day"].isin(HOLIDAYS).astype(int)
    d["in_summer"] = (d["month_day"] >= SUMMER[0]) & (d["month_day"] <= SUMMER[1])
    return d


def weather_climatology(meteo: pd.DataFrame, years=TRAINING_YEARS) -> pd.Series:
    """A1: mean tmax per month over the climatology years."""
    m = meteo[meteo["date"].dt.year.isin(years)]
    return m.groupby(m["date"].dt.month)["tmax"].mean()


def add_weather(d: pd.DataFrame, climatology: pd.Series) -> pd.DataFrame:
    """D10, A1: tmax anomaly and weather class."""
    d = d.copy()
    d["tmax_anomaly"] = d["tmax"] - d["date"].dt.month.map(climatology)
    d["weather"] = np.where(d["rain_mm"] >= RAINY_MM, "rainy",
                            np.where(d["tmax_anomaly"] < -COOL_DEGREES, "cool", "good"))
    d.loc[d["tmax"].isna() | d["rain_mm"].isna(), "weather"] = None
    return d


def training_days(daily: pd.DataFrame) -> pd.DataFrame:
    """D7: summer days of the training years with presences and weather."""
    t = daily[daily["in_summer"] & daily["year"].isin(TRAINING_YEARS)]
    if t[[*PRESENCES, *WEATHER_FEATURES]].isna().any().any():
        raise ValueError("Training days with missing presences or weather")
    return t.reset_index(drop=True)


# ------------------------------------------------------------------ main estimator (D9)
def fit_gbm(train: pd.DataFrame, y: str, features=GBM_FEATURES):
    """Model on all the training days and the SD of its out-of-fold residuals, one training year
    left out at a time (D12)."""
    x = train[features].astype(float)
    model = HistGradientBoostingRegressor(**GBM_PARAMS).fit(x, train[y])
    oof = np.empty(len(train))
    for year in train["year"].unique():
        out = (train["year"] == year).values
        oof[out] = HistGradientBoostingRegressor(**GBM_PARAMS).fit(x[~out], train[y][~out]).predict(x[out])
    return model, float(np.std(train[y].values - oof))


def summer_calendar(year: int = 2025) -> pd.DataFrame:
    """The summer calendar days (``month_day``), crossed with every weekday."""
    dates = pd.date_range(f"{year}-{SUMMER[0]}", f"{year}-{SUMMER[1]}")
    days = add_calendar(pd.DataFrame({"date": dates})).drop(columns=["weekday", "year", "date", "in_summer"])
    return days.merge(pd.DataFrame({"weekday": range(7)}), how="cross")


def gbm_presence_stats(train: pd.DataFrame) -> pd.DataFrame:
    """Per calendar day x weekday x weather class: mean and SD of tourists and excursionists."""
    cal = summer_calendar()
    weather_days = train[["month", "weather", *WEATHER_FEATURES]]
    rows = cal.merge(weather_days, on="month")  # each cell x the observed weather days of its class (A4)
    keys = ["month_day", "summer_day", "month", "weekday", "weather"]
    out = None
    for y in PRESENCES:
        model, resid_sd = fit_gbm(train, y)
        rows[y] = model.predict(rows[GBM_FEATURES].astype(float))
        g = rows.groupby(keys)[y].agg(["mean", "std", "size"])
        g["std"] = np.sqrt(g["std"].fillna(0.0) ** 2 + resid_sd ** 2)
        g = g.rename(columns={"mean": f"mean_{y}", "std": f"std_{y}", "size": "weather_days"})
        out = g if out is None else out.join(g.drop(columns="weather_days"))
    out = out.reset_index()
    out["weekday"] = out["weekday"].map(dict(enumerate(WEEKDAYS)))
    return out.sort_values(["summer_day", "weekday", "weather"]).reset_index(drop=True)


# ------------------------------------------------------------------ comparison estimator (D9)
def _design(d: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame({"month_weekday": d["month"].astype(str) + "_" + d["weekday"].astype(str),
                      "weather": pd.Categorical(d["weather"], categories=WEATHER_CLASSES)}, index=d.index)
    return pd.get_dummies(x).astype(float)


def fit_additive(train: pd.DataFrame, y: str):
    """Least squares on month x weekday + weather class; returns (coefficients, columns, residual SD)."""
    x = _design(train)
    coef, *_ = np.linalg.lstsq(x.values, train[y].values, rcond=None)
    resid = train[y].values - x.values @ coef
    return coef, x.columns, float(resid.std(ddof=np.linalg.matrix_rank(x.values)))


def predict_additive(fitted, d: pd.DataFrame) -> np.ndarray:
    coef, columns, _ = fitted
    return _design(d).reindex(columns=columns, fill_value=0.0).values @ coef


def additive_presence_stats(train: pd.DataFrame) -> pd.DataFrame:
    """Per month x weekday x weather class: mean and SD of tourists and excursionists."""
    cells = pd.MultiIndex.from_product(
        [sorted(train["month"].unique()), range(7), WEATHER_CLASSES], names=["month", "weekday", "weather"]
    ).to_frame(index=False)
    for y in PRESENCES:
        fitted = fit_additive(train, y)
        cells[f"mean_{y}"] = predict_additive(fitted, cells)
        cells[f"std_{y}"] = fitted[2]
    cells["weekday"] = cells["weekday"].map(dict(enumerate(WEEKDAYS)))
    return cells[["month", "weekday", "weather", *(f"{s}_{y}" for y in PRESENCES for s in ("mean", "std"))]]


def weather_frequencies(daily: pd.DataFrame) -> pd.DataFrame:
    """A5: per summer month, the share of days of each weather class in the training years."""
    t = training_days(daily)
    freq = pd.crosstab(t["month"], t["weather"], normalize="index").reindex(columns=list(WEATHER_CLASSES), fill_value=0.0)
    return freq.stack().rename("freq_rel").reset_index()
