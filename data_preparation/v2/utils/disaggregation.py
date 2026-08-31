import logging

import numpy as np
import pandas as pd


def _key(series, is_time=False, freq=None):
    """Normalize a join key: 22001 / '22001' / '022001' match, dates are compared
    at the given period granularity (`freq`) or by day."""
    if not is_time:
        return series.astype(str).str.strip().str.lstrip("0")
    t = pd.to_datetime(series.astype(str), errors="coerce")
    return t.dt.to_period(freq).astype(str) if freq else t.dt.strftime("%Y-%m-%d")


def _lookup_weights(exp, weights, on, weight_col, time_col, freq=None):
    """Raw weight of every exploded row (NaN when the key has no match)."""
    if weights is None:
        return np.ones(len(exp))
    if weight_col is None:
        raise ValueError("weight_col is required when weights is provided")

    left, right, keys = exp.copy(), weights.copy(), []
    for c in on:
        k = f"_K_{c}"
        left[k] = _key(left[c], c == time_col, freq)
        right[k] = _key(right[c], c == time_col, freq)
        keys.append(k)

    # collapse the distribution on the join keys so the merge cannot duplicate rows
    right = right.groupby(keys, as_index=False)[weight_col].sum()
    merged = left[keys].merge(right, on=keys, how="left")
    return merged[weight_col].to_numpy()


def _largest_remainder(groups, shares):
    """Round shares to integers preserving each group total (largest remainder)."""
    t = pd.DataFrame(
        {
            "g": np.asarray(groups),
            "s": pd.to_numeric(shares, errors="coerce").to_numpy(),
        }
    )
    t["f"] = np.floor(t["s"].fillna(0))
    t["r"] = t["s"].fillna(0) - t["f"]
    rank = t.groupby("g")["r"].rank(method="first", ascending=False)
    left = (
        t.groupby("g")["s"].transform("sum").round()
        - t.groupby("g")["f"].transform("sum")
    ).clip(lower=0)
    out = t["f"] + (rank <= left).astype(float)
    return pd.Series(np.where(t["s"].isna(), np.nan, out), index=shares.index)


def _split(exp, cols, integer):
    """Split each parent row (_STEP) among its children proportionally to _W."""
    exp["_W"] = pd.to_numeric(exp["_W"], errors="coerce").fillna(0.0).clip(lower=0)
    denom = exp.groupby("_STEP")["_W"].transform("sum")
    size = exp.groupby("_STEP")["_W"].transform("size")
    # parents whose weights are all zero/missing fall back to a uniform split
    frac = np.where(denom > 0, exp["_W"] / denom.where(denom > 0, 1), 1 / size)

    for c in cols:
        val = pd.to_numeric(exp[c], errors="coerce") * frac
        exp[c] = _largest_remainder(exp["_ROW"], val) if integer else val
    return exp


def _open(df):
    """Tag parent rows. _ROW is created only if the caller has not already."""
    exp = df.copy()
    own_row = "_ROW" not in exp.columns
    if own_row:
        exp["_ROW"] = np.arange(len(exp))
    exp["_STEP"] = np.arange(len(exp))
    return exp, own_row


def _close(exp, own_row):
    drop = ["_STEP", "_W"] + (["_ROW"] if own_row else [])
    return exp.drop(columns=drop).reset_index(drop=True)


def disaggregate_space(
    df,
    cols,
    *,
    id_col="ID_COMUNE",
    group_col="LOCATION",
    space_map=None,
    weights=None,
    weight_col=None,
    time_col="DATA",
    time_freq=None,
    id_to_name=None,
    integer=True,
):
    """Expand rows holding several target ids into one row per id.

    space_map: optional {source_area: [ids]} applied on group_col when id_col
    does not already contain the list of targets.
    time_freq: granularity at which weights are aggregated before the join
    (e.g. "M" to weight a monthly row with a daily distribution).
    """
    exp, own_row = _open(df)
    if space_map is not None:
        exp[id_col] = exp[group_col].map(space_map)
    exp = exp.explode(id_col)

    on = [id_col]
    if weights is not None and time_col in weights.columns and time_col in exp.columns:
        on.append(time_col)
    exp["_W"] = _lookup_weights(exp, weights, on, weight_col, time_col, time_freq)

    exp = _split(exp, cols, integer)
    if id_to_name is not None:
        exp[group_col] = exp[id_col].map(id_to_name)
    return _close(exp, own_row)


def disaggregate_time(
    df,
    cols,
    *,
    freq_from="M",
    freq_to="D",
    time_col="DATA",
    id_col="ID_COMUNE",
    weights=None,
    weight_col=None,
    weight_freq=None,
    integer=True,
):
    """Expand each row into one row per child period (freq_from -> freq_to)."""
    exp, own_row = _open(df)
    periods = pd.to_datetime(exp[time_col].astype(str), errors="coerce").dt.to_period(
        freq_from
    )
    exp[time_col] = [
        pd.period_range(p.start_time, p.end_time, freq=freq_to) if pd.notna(p) else []
        for p in periods
    ]
    exp = exp.explode(time_col)
    exp[time_col] = exp[time_col].apply(
        lambda p: p.start_time if pd.notna(p) else pd.NaT
    )

    on = [time_col]
    if weights is not None and id_col in weights.columns and id_col in exp.columns:
        on.append(id_col)
    exp["_W"] = _lookup_weights(exp, weights, on, weight_col, time_col, weight_freq)

    exp = _split(exp, cols, integer)
    return _close(exp, own_row)


def disaggregate(
    df,
    cols,
    axis="both",
    *,
    space_weights=None,
    space_weight_col=None,
    space_map=None,
    space_time_freq=None,
    time_weights=None,
    time_weight_col=None,
    time_weight_freq=None,
    freq_from="M",
    freq_to="D",
    id_col="ID_COMUNE",
    group_col="LOCATION",
    time_col="DATA",
    id_to_name=None,
    integer=True,
):
    """Disaggregate along axis in {"space", "time", "both"}"""
    if axis not in {"space", "time", "both"}:
        raise ValueError(f"Unknown axis: {axis}")

    both = axis == "both"
    if both:
        df = df.copy()
        df["_ROW"] = np.arange(len(df))

    if axis in {"space", "both"}:
        df = disaggregate_space(
            df,
            cols,
            id_col=id_col,
            group_col=group_col,
            space_map=space_map,
            weights=space_weights,
            weight_col=space_weight_col,
            time_col=time_col,
            time_freq=space_time_freq,
            id_to_name=id_to_name,
            integer=integer and not both,
        )

    if axis in {"time", "both"}:
        df = disaggregate_time(
            df,
            cols,
            freq_from=freq_from,
            freq_to=freq_to,
            time_col=time_col,
            id_col=id_col,
            weights=time_weights,
            weight_col=time_weight_col,
            weight_freq=time_weight_freq,
            integer=integer,
        )

    return df.drop(columns="_ROW") if both else df
