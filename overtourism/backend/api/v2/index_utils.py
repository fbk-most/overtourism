from __future__ import annotations

from datetime import timedelta
import geopandas as gpd

# ---------------------------------------------------------------------------
# Map response helpers
# ---------------------------------------------------------------------------


def _empty_map_response(gdf_base):
    gdf_base["INDICE"] = -1
    return {"geojson": gdf_base.to_json(), "min_value": -1, "max_value": -1}


def _build_geodataframe(gdf_base, result, join_on="ID_COMUNE", area_name_col="COMUNE"):
    return gpd.GeoDataFrame(
        gdf_base[["PRO_COM_T", "COMUNE", "geometry"]]
        .merge(result, left_on="PRO_COM_T", right_on=join_on, how="left")
        .rename(columns={area_name_col: "AREA_NAME"})
        .drop(columns=["PRO_COM_T", join_on]),
        geometry="geometry",
        crs=gdf_base.crs,
    )


def _compute_min_max(gdf_final):
    # Comupute min amd max and can clamp the minimum to 0.0 when it is less than or equal to 1
    try:
        min_val = float(gdf_final["INDICE"].min())
        max_val = float(gdf_final["INDICE"].max())

        if min_val <= 1:
            min_val = 0.0

        return min_val, max_val
    except Exception:
        return -1, -1


def _to_map_response(gdf_final):
    min_value, max_value = _compute_min_max(gdf_final)
    return {
        "geojson": gdf_final.to_json(),
        "min_value": min_value,
        "max_value": max_value,
    }


# ---------------------------------------------------------------------------
# Chart labels
# ---------------------------------------------------------------------------


def get_chart_labels(start_date, end_date, granularity: str) -> list[str]:
    if granularity == "giornaliero":
        labels, cur = [], start_date
        while cur <= end_date:
            labels.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)

    elif granularity == "mensile":
        labels, cur = [], start_date.replace(day=1)
        while cur <= end_date:
            labels.append(cur.strftime("%Y-%m"))
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

    else:  # annuale
        labels = [str(y) for y in range(start_date.year, end_date.year + 1)]

    return labels
