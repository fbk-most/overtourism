# SPDX-License-Identifier: Apache-2.0
"""Distribution of monthly presences (area level) over comuni and days, taking the length of stay into account.

Monthly arrivals A and presences P (nights) of an area give the average stay of the month, s = P / A.
Presences cannot be spread uniformly over the days: a guest who arrives on day d is present on the
days d, d+1, ..., d+s-1 (also across the end of the month). The model, for every area:

  1. the arrivals of a month are spread uniformly over its days (A / days per day);
  2. every arrival of day d adds presences on the following days: 1 per day for s days
     (the fractional part of s counts for the last day), so the stay of the month of arrival is used;
  3. the daily presences are the sum of these contributions; they include the stays that started in the
     previous month (spill-over);
  4. the daily values of each month are rescaled so that they add up exactly to the official P of the month
     (and rounded to integers with the largest remainder method, keeping the monthly total);
  5. the area x day presences are split over the comuni of the area proportionally to their beds.

The arrivals are only used to compute the stay: they are not part of the output.
"""

import logging

import numpy as np
import pandas as pd

from utils.disaggregation import (
    _largest_remainder,
    assert_sums_match,
    beds_weights,
    disaggregate,
    is_whole,
)

logger = logging.getLogger(__name__)


def _area_daily_presences(months, arrivals, presences, area, spill_over=True):
    """Daily presences of one area. `months`: sorted month starts; `arrivals`, `presences`: aligned arrays.
    Returns a DataFrame (DATA, presenze, MONTH) whose monthly sums are exactly the input presences.
    """
    full = pd.period_range(months[0], months[-1], freq="M")
    if len(full) != len(months):
        logger.warning(
            "[%s] months missing between %s and %s: treated as no arrivals",
            area,
            full[0],
            full[-1],
        )
    a_m = pd.Series(arrivals, index=pd.PeriodIndex(months, freq="M")).reindex(
        full, fill_value=0.0
    )
    p_m = pd.Series(presences, index=pd.PeriodIndex(months, freq="M")).reindex(
        full, fill_value=0.0
    )

    no_arrivals = (a_m <= 0) & (p_m > 0)
    if no_arrivals.any():
        logger.warning(
            "[%s] presences without arrivals in %s: stay set to 1 night",
            area,
            [str(m) for m in a_m.index[no_arrivals]],
        )
        a_m[no_arrivals] = p_m[no_arrivals]
    stay = (p_m / a_m.where(a_m > 0)).fillna(1.0)

    # warm-up: a virtual month before the first one with the same arrivals / stay (only for the spill-over)
    first = full[0] - 1
    full = full.insert(0, first)
    a_m = pd.concat([pd.Series([a_m.iloc[0]], index=[first]), a_m])
    p_m = pd.concat([pd.Series([p_m.iloc[0]], index=[first]), p_m])
    stay = pd.concat([pd.Series([stay.iloc[0]], index=[first]), stay])

    n_days = full.days_in_month.to_numpy()
    arrivals_day = np.repeat((a_m / n_days).to_numpy(), n_days)
    stay_day = np.repeat(stay.to_numpy(), n_days)
    n = len(arrivals_day)

    month_of_day = np.repeat(np.arange(len(full)), n_days)
    model = np.zeros(n)
    for k in range(int(np.ceil(stay_day.max())) + 1):
        w = (
            np.clip(stay_day - k, 0.0, 1.0) * arrivals_day
        )  # presences k days after the arrival
        if not spill_over:  # only the days of the month of the arrival
            w = w[: n - k] * (month_of_day[: n - k] == month_of_day[k:])
            model[k:] += w
        else:
            model[k:] += w[: n - k]

    starts = np.r_[0, np.cumsum(n_days)[:-1]]
    model_m = np.add.reduceat(model, starts)
    factor = np.divide(
        p_m.to_numpy(), model_m, out=np.zeros(len(model_m)), where=model_m > 0
    )
    daily = model * np.repeat(factor, n_days)

    days = pd.to_datetime(
        np.concatenate(
            [
                pd.date_range(m.start_time, m.end_time.normalize(), freq="D")
                for m in full
            ]
        )
    )
    out = pd.DataFrame(
        {"DATA": days, "presenze": daily, "MONTH": full[month_of_day].astype(str)}
    )
    out = out[month_of_day > 0]  # without the warm-up month
    ratio = (model_m / np.where(p_m.to_numpy() > 0, p_m.to_numpy(), np.nan))[1:]
    return out.reset_index(drop=True), ratio


def distribute_by_stay(
    arrivals,
    presences,
    area_ids,
    beds,
    *,
    bed_col,
    out_col,
    keep_from=None,
    spill_over=True,
    check=True,
):
    """Monthly area presences -> comune x day presences (see the module docstring).

    arrivals, presences  long frames (AREA, DATA = month start, value) with the same areas and months.
    area_ids             {area: [ids of its comuni]}.
    beds                 (DATA = year, ID_COMUNE, bed_col): weights of the split among comuni
                         (the year of the day, or the nearest available year, is used).
    keep_from            only the months from this date are returned (earlier months are context
                         for the spill-over of the following ones).
    spill_over           True: stays cross the end of the month (the first days of a month also contain the guests
                         arrived in the previous one); False: every month only uses its own arrivals and stay.
    The sum of the output is checked against the input presences of every area and month.
    """
    a = arrivals.rename(columns={"value": "A"})
    p = presences.rename(columns={"value": "P"})
    t = a.merge(p, on=["AREA", "DATA"], how="outer", validate="one_to_one")
    if t[["A", "P"]].isna().any().any():
        bad = t.loc[t[["A", "P"]].isna().any(axis=1), ["AREA", "DATA"]].head()
        raise ValueError(
            f"arrivals and presences do not cover the same areas / months:\n{bad}"
        )
    unknown = set(t["AREA"]) - set(area_ids)
    if unknown:
        raise ValueError(f"areas without comuni: {sorted(unknown)}")

    frames, ratios = [], []
    for area, g in t.sort_values("DATA").groupby("AREA"):
        d, r = _area_daily_presences(
            g["DATA"].to_numpy(),
            g["A"].to_numpy(float),
            g["P"].to_numpy(float),
            area,
            spill_over,
        )
        d["AREA"] = area
        frames.append(d)
        ratios.append(r)
    daily = pd.concat(frames, ignore_index=True)
    ratios = np.concatenate(ratios)
    ratios = ratios[np.isfinite(ratios)]
    logger.info(
        "[stay] model monthly total / official total (before rescaling): min %.2f, median %.2f, max %.2f",
        ratios.min(),
        np.median(ratios),
        ratios.max(),
    )

    if keep_from is not None:
        daily = daily[daily["DATA"] >= pd.Timestamp(keep_from)]
        t = t[t["DATA"] >= pd.Timestamp(keep_from)]
    daily = daily.reset_index(drop=True)

    # integer values: largest remainder inside every (area, month), the monthly total is kept
    integer = is_whole(t, ["P"])
    if integer:
        grp = (daily["AREA"] + "|" + daily["MONTH"]).to_numpy()
        daily["presenze"] = _largest_remainder(grp, daily["presenze"]).astype(np.int64)

    # one id per (area, month): survives the split over comuni, used to sum back
    key = daily["AREA"] + "|" + daily["MONTH"]
    daily["_TID"] = pd.factorize(key)[0]
    expected = (
        daily[["_TID", "AREA", "MONTH"]]
        .drop_duplicates()
        .merge(
            t.assign(MONTH=t["DATA"].dt.to_period("M").astype(str)),
            on=["AREA", "MONTH"],
        )[["_TID", "P"]]
        .rename(columns={"P": "presenze"})
    )

    daily["ID_COMUNE"] = daily["AREA"].map(
        {k: sorted({str(int(i)).zfill(6) for i in v}) for k, v in area_ids.items()}
    )
    daily["DATA"] = daily["DATA"].dt.strftime("%Y-%m-%d")
    years = pd.to_datetime(daily["DATA"]).dt.year.unique()
    out = disaggregate(
        daily[["DATA", "ID_COMUNE", "presenze", "_TID"]],
        ["presenze"],
        axis="space",
        space_weights=beds_weights(beds, years, bed_col),
        space_weight_col=bed_col,
        space_time_freq="Y",
        integer=integer,
    )

    if check:
        assert_sums_match(expected, out, ["presenze"], ["_TID"], name=f"stay/{out_col}")
    if integer:
        out["presenze"] = out["presenze"].astype(np.int64)
    out = out.drop(columns="_TID").rename(columns={"presenze": out_col})
    return out[["DATA", "ID_COMUNE", out_col]].reset_index(drop=True)
