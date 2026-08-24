"""Presence statistics for the Fazzon (Lago dei Caprioli, Val di Sole) overtourism model.

Two presence variables are modelled:

``pv_visitors_car``
    Daily visitors arriving by private car.  Derived from 2025 Fazzon parking-ticket
    data by applying **PERSONS_PER_CAR = 2.83** (NetMobility 2021 field study).
    Season means and within-cell standard deviations are calibrated from daily
    parking-ticket counts aggregated over the 2025 regulated season (81 days,
    June–September).

``pv_visitors_other``
    Daily visitors arriving by non-car modes (shuttle bus, on foot, bicycle).
    All values are **ASSUMPTION** — no 2025 non-car count data are available.
    Derived from ``pv_visitors_car`` by applying the non-car fraction from the
    2022 EETRA modal-split survey (**NON_CAR_SHARE = 0.31**, non-car share of
    total visitors; ratio of non-car to car visitors ≈ 0.449).  Within-cell
    standard deviations are set to 50 % of the cell mean (synthetic ASSUMPTION).

Additive decomposition::

    mean_total = season_mean + day_type_correction(season, day_type)
    var_total  = within_cell_var(season)

Unlike Portofino, there is no weather CV (no weather labels in any Fazzon dataset).

Day-type structure (see :data:`DAY_TYPE_BUCKETS`):

* **july**:      peak = sunday only;         base = Mon–Sat (6 days)
* **august**:    peak = monday + tuesday;    base = Wed–Sun (5 days)
* **june**:      peak = saturday + sunday;   base = Mon–Fri (5 days)  — ASSUMPTION
* **september**: peak = saturday + sunday;   base = Mon–Fri (5 days)  — ASSUMPTION

Day-type corrections reflect the **day-of-week inversion** observed in the 2025
Fazzon parking data: August peaks counter-intuitively on Monday–Tuesday (start of
the working week when families rotate), while July peaks on Sunday.  June and
September have insufficient data for calibration; the peak bucket defaults to the
conventional weekend (ASSUMPTION).
"""

# SPDX-License-Identifier: Apache-2.0

import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

PERSONS_PER_CAR: float = 2.83
"""Average vehicle occupancy at Fazzon (NetMobility 2021 field study)."""

NON_CAR_SHARE: float = 0.31
"""Non-car modal share of total visitors (2022 EETRA survey).

Flagged as **ASSUMPTION** for 2025: no direct non-car count data are available
for the regulated season.  The ratio of non-car to car visitors is
NON_CAR_SHARE / (1 − NON_CAR_SHARE) ≈ 0.449.
"""

_OTHER_RATIO: float = NON_CAR_SHARE / (1.0 - NON_CAR_SHARE)  # ≈ 0.449  ASSUMPTION

# ---------------------------------------------------------------------------
# Day-type bucket definitions  (parametric)
# ---------------------------------------------------------------------------

DAY_TYPE_BUCKETS: dict[str, dict[str, list[str]]] = {
    "july": {
        "peak": ["sunday"],
        "base": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
    },
    "august": {
        "peak": ["monday", "tuesday"],
        "base": ["wednesday", "thursday", "friday", "saturday", "sunday"],
    },
    # No 2025 day-of-week data for June and September → ASSUMPTION: conventional weekend peak
    "june": {
        "peak": ["saturday", "sunday"],  # ASSUMPTION
        "base": ["monday", "tuesday", "wednesday", "thursday", "friday"],  # ASSUMPTION
    },
    "september": {
        "peak": ["saturday", "sunday"],  # ASSUMPTION
        "base": ["monday", "tuesday", "wednesday", "thursday", "friday"],  # ASSUMPTION
    },
}
"""Day-of-week classification per season.

Only July and August entries are calibrated from 2025 parking data.
June and September entries are **ASSUMPTION** (conventional weekend peak);
update this dict when day-of-week data become available for those seasons.
"""

# ---------------------------------------------------------------------------
# Season stats
# ---------------------------------------------------------------------------
# Source: 2025 Fazzon parking-ticket data.
#   Daily parking tickets → ×PERSONS_PER_CAR → pv_visitors_car
#   pv_visitors_other = pv_visitors_car × _OTHER_RATIO  (ASSUMPTION; see module docstring)
#   std_other_visitors = mean_other_visitors × 0.50     (ASSUMPTION; 50% relative SD)
#
# Raw daily parking-ticket statistics (2025 regulated season, n=81 days):
#   june      n= 3   mean_tickets=212  sd_tickets=110   freq_rel= 3/81
#   july      n=31   mean_tickets=176  sd_tickets= 54   freq_rel=31/81
#   august    n=30   mean_tickets=279  sd_tickets= 95   freq_rel=30/81
#   september n=17   mean_tickets= 80  sd_tickets= 42   freq_rel=17/81
#
# std values stored here = within-cell residual std (after removing the season
# mean AND the per-season day-type correction from each observation).

season_stats = pd.DataFrame(
    [
        {
            "cluster_name": "june",
            "freq_rel": 3 / 81,
            "mean_car_visitors": 600.0,  # 212 tickets × 2.83
            "std_car_visitors": 311.3,  # 110 × 2.83   within-cell residual std
            "mean_other_visitors": 269.4,  # 600.0 × 0.449   ASSUMPTION
            "std_other_visitors": 134.7,  # 269.4 × 0.50    ASSUMPTION  50% relative SD
        },
        {
            "cluster_name": "july",
            "freq_rel": 31 / 81,
            "mean_car_visitors": 498.1,  # 176 × 2.83
            "std_car_visitors": 152.8,  # 54 × 2.83    within-cell residual std
            "mean_other_visitors": 223.6,  # 498.1 × 0.449   ASSUMPTION
            "std_other_visitors": 111.8,  # 223.6 × 0.50    ASSUMPTION  50% relative SD
        },
        {
            "cluster_name": "august",
            "freq_rel": 30 / 81,
            "mean_car_visitors": 789.6,  # 279 × 2.83
            "std_car_visitors": 268.9,  # 95 × 2.83    within-cell residual std
            "mean_other_visitors": 354.5,  # 789.6 × 0.449   ASSUMPTION
            "std_other_visitors": 177.3,  # 354.5 × 0.50    ASSUMPTION  50% relative SD
        },
        {
            "cluster_name": "september",
            "freq_rel": 17 / 81,
            "mean_car_visitors": 226.4,  # 80 × 2.83
            "std_car_visitors": 118.9,  # 42 × 2.83    within-cell residual std
            "mean_other_visitors": 101.6,  # 226.4 × 0.449   ASSUMPTION
            "std_other_visitors": 50.8,  # 101.6 × 0.50    ASSUMPTION  50% relative SD
        },
    ]
).set_index("cluster_name")

# ---------------------------------------------------------------------------
# Day-type stats
# ---------------------------------------------------------------------------
# Corrections are per-season residuals from the season mean (in person-counts).
# Frequency-weighted mean ≈ 0 by construction for each season.
#
# July   (peak=sunday, freq_rel=1/7):
#   sunday_mean_tickets=232, july_mean_tickets=176 → car-correction = +56 tickets
#   peak (sunday) : +56 × 2.83 = +158.5 person-visits
#   base (6 days) : −(1/6) × 56 × 2.83 ≈ −26.3 person-visits
#   zero-mean check: (1/7)×(+56) + (6/7)×(−9.3) ≈ 0 ✓
#   other corrections = car corrections × 0.449  (ASSUMPTION)
#
# August (peak=monday+tuesday, freq_rel=2/7):
#   mon+tue_mean_tickets=319, august_mean_tickets=279 → car-correction = +40 tickets
#   peak (2 days): +40 × 2.83 = +113.2 person-visits
#   base (5 days): −16 × 2.83 = −45.3 person-visits
#   zero-mean check: (2/7)×(+40) + (5/7)×(−16) = 80/7 − 80/7 = 0 ✓
#   other corrections = car corrections × 0.449  (ASSUMPTION)
#
# June, September: zero corrections — ASSUMPTION (no day-of-week data)

day_type_stats = pd.DataFrame(
    [
        {
            "season": "june",
            "day_type": "peak",
            "freq_rel": 2.0 / 7.0,
            "mean_car_visitors": 0.0,
            "mean_other_visitors": 0.0,  # ASSUMPTION
        },
        {
            "season": "june",
            "day_type": "base",
            "freq_rel": 5.0 / 7.0,
            "mean_car_visitors": 0.0,
            "mean_other_visitors": 0.0,  # ASSUMPTION
        },
        {
            "season": "july",
            "day_type": "peak",
            "freq_rel": 1.0 / 7.0,
            "mean_car_visitors": +158.5,
            "mean_other_visitors": +71.2,  # +71.2 ASSUMPTION
        },
        {
            "season": "july",
            "day_type": "base",
            "freq_rel": 6.0 / 7.0,
            "mean_car_visitors": -26.3,
            "mean_other_visitors": -11.8,  # -11.8 ASSUMPTION
        },
        {
            "season": "august",
            "day_type": "peak",
            "freq_rel": 2.0 / 7.0,
            "mean_car_visitors": +113.2,
            "mean_other_visitors": +50.8,  # +50.8 ASSUMPTION
        },
        {
            "season": "august",
            "day_type": "base",
            "freq_rel": 5.0 / 7.0,
            "mean_car_visitors": -45.3,
            "mean_other_visitors": -20.3,  # -20.3 ASSUMPTION
        },
        {
            "season": "september",
            "day_type": "peak",
            "freq_rel": 2.0 / 7.0,
            "mean_car_visitors": 0.0,
            "mean_other_visitors": 0.0,  # ASSUMPTION
        },
        {
            "season": "september",
            "day_type": "base",
            "freq_rel": 5.0 / 7.0,
            "mean_car_visitors": 0.0,
            "mean_other_visitors": 0.0,  # ASSUMPTION
        },
    ]
).set_index(["season", "day_type"])

# ---------------------------------------------------------------------------
# CV weight dicts  — consumed by CategoricalIndex constructors in the model
# ---------------------------------------------------------------------------

season = {s: season_stats.loc[s, "freq_rel"] for s in season_stats.index}

# day_type weights: peak=2/7, base=5/7.
# The August bucket definition (peak=Mon+Tue, 2 days) gives the natural 2/7
# peak weight.  July has peak=1/7 but 2/7 is used as a cross-season central
# estimate consistent with the calendar share of a 2-day peak bucket.
# ASSUMPTION — adjust if season weights are required to vary across seasons.
day_type: dict[str, float] = {"peak": 2.0 / 7.0, "base": 5.0 / 7.0}  # ASSUMPTION

# ---------------------------------------------------------------------------
# Conditional distribution factories
# ---------------------------------------------------------------------------


def make_presence_factories(
    yr_season_stats: pd.DataFrame,
    yr_day_type_stats: pd.DataFrame,
):
    """Return ``(car_visitors_stats, other_visitors_stats)`` closures for the given stats.

    Both factories use the supplied season and day-type DataFrames for their
    cell means, and the within-cell variance stored in *yr_season_stats*.

    There is no weather CV for Fazzon (no weather labels in any source dataset).
    The variance decomposition is therefore simpler than Portofino::

        var_total = within_cell_var(season)

    The day-type correction shifts only the **mean**; its variance is already
    captured inside the within-cell residual variance.

    The distributions are **Gamma**, parameterised by the combined mean μ and
    variance σ²::

        k = μ² / σ²   (shape)
        θ = σ² / μ    (scale)

    Gamma is naturally supported on (0, ∞) with a smooth density at 0.  The
    mean is floored at 1.0 before computing Gamma parameters to guard against
    negative cell means (e.g. a small-n June base-day combination).
    """

    def _gamma(mean: float, var: float):
        mean = max(mean, 1.0)  # guard against rare low-season base-day negatives
        k = mean**2 / var
        theta = var / mean
        return stats.gamma(a=k, scale=theta)

    def car_visitors_stats(day_type: str, season: str):
        mean = float(yr_season_stats.loc[season, "mean_car_visitors"])
        var = float(yr_season_stats.loc[season, "std_car_visitors"]) ** 2
        mean += float(yr_day_type_stats.loc[(season, day_type), "mean_car_visitors"])
        return _gamma(mean, var)

    def other_visitors_stats(day_type: str, season: str):
        mean = float(yr_season_stats.loc[season, "mean_other_visitors"])
        var = float(yr_season_stats.loc[season, "std_other_visitors"]) ** 2
        mean += float(yr_day_type_stats.loc[(season, day_type), "mean_other_visitors"])
        return _gamma(mean, var)

    return car_visitors_stats, other_visitors_stats


# Default module-level factories (2025 calibrated stats)
car_visitors_stats, other_visitors_stats = make_presence_factories(season_stats, day_type_stats)
