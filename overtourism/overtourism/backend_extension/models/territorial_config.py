"""Territorial granularity configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Granularity = Literal["comune", "macro_area"]
Aggregation = Literal["mean", "sum"]


@dataclass(frozen=True)
class MacroArea:
    """A named province-level group of comuni."""

    name: str
    comuni: list[str]


@dataclass
class TerritorialConfig:
    """
    Request-scoped territorial configuration.
    """

    areas: list[MacroArea] = field(default_factory=list)
    spatial_granularity: Granularity = "comune"
    allowed_comuni: set[str] | None = None
    macro_area_agg: Aggregation = "mean"

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        areas: list[MacroArea],
        spatial_granularity: str = "comune",
        allowed_comuni: set[str] | None = None,
        macro_area_agg: str = "mean",
    ) -> "TerritorialConfig":
        """Validated constructor used by all endpoints."""

        if spatial_granularity not in ("comune", "macro_area"):
            raise ValueError(
                f"Unknown spatial_granularity={spatial_granularity!r}. "
                "Expected 'comune' or 'macro_area'."
            )

        if macro_area_agg not in ("mean", "sum"):
            raise ValueError(
                f"Unknown macro_area_agg={macro_area_agg!r}. "
                "Expected 'mean' or 'sum'."
            )

        return cls(
            areas=areas,
            spatial_granularity=spatial_granularity,
            allowed_comuni=allowed_comuni,
            macro_area_agg=macro_area_agg,
        )

    # ------------------------------------------------------------------
    # Core: filter + aggregate
    # ------------------------------------------------------------------

    def filter_comuni(
        self,
        df: pd.DataFrame,
        id_col: str = "ID_COMUNE",
    ) -> pd.DataFrame:
        """Apply the permission filter."""

        if self.allowed_comuni is None:
            return df

        return df[df[id_col].astype(str).isin(self.allowed_comuni)].copy()

    def aggregate_to_macro_areas(
        self,
        df: pd.DataFrame,
        value_col: str = "INDICE",
        id_col: str = "ID_COMUNE",
    ) -> pd.DataFrame:
        """Aggregate a comune dataframe into macro areas."""

        present = set(df[id_col].astype(str))
        rows = []

        for area in self.areas:
            members = [c for c in area.comuni if c in present]

            if not members:
                rows.append(
                    {
                        id_col: area.name,
                        value_col: float("nan"),
                    }
                )
                continue

            subset = df[df[id_col].astype(str).isin(members)][value_col]

            if self.macro_area_agg == "mean":
                value = float(subset.mean())
            else:
                value = float(subset.sum())

            rows.append(
                {
                    id_col: area.name,
                    value_col: value,
                }
            )

        return pd.DataFrame(rows)

    def apply(
        self,
        df: pd.DataFrame,
        value_col: str = "INDICE",
        id_col: str = "ID_COMUNE",
    ) -> pd.DataFrame:
        """Filter and optionally aggregate."""

        filtered = self.filter_comuni(df, id_col=id_col)

        if self.spatial_granularity == "macro_area":
            return self.aggregate_to_macro_areas(
                filtered,
                value_col=value_col,
                id_col=id_col,
            )

        return filtered

    # ------------------------------------------------------------------
    # Time series
    # ------------------------------------------------------------------

    def apply_to_series(
        self,
        series: list[dict],
        label_key: str = "label",
        data_key: str = "data",
        std_key: str = "std",
    ) -> list[dict]:
        """Apply filtering/aggregation to temporal series."""

        import numpy as np

        region_series = [s for s in series if str(s[label_key]) == "-1"]
        comune_series = [s for s in series if str(s[label_key]) != "-1"]

        if self.allowed_comuni is not None:
            comune_series = [
                s for s in comune_series if str(s[label_key]) in self.allowed_comuni
            ]

        if self.spatial_granularity == "comune":
            return comune_series + region_series

        by_comune = {str(s[label_key]): s for s in comune_series}

        agg_fn = np.mean if self.macro_area_agg == "mean" else np.sum

        area_series = []

        for area in self.areas:
            members = [c for c in area.comuni if c in by_comune]

            if not members:
                continue

            data = np.array([by_comune[c][data_key] for c in members])
            std = np.array([by_comune[c][std_key] for c in members])

            area_series.append(
                {
                    label_key: area.name,
                    data_key: [round(float(x), 2) for x in agg_fn(data, axis=0)],
                    std_key: [round(float(x), 2) for x in np.mean(std, axis=0)],
                }
            )

        return area_series + region_series
