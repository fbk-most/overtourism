from __future__ import annotations

from pathlib import Path
from functools import lru_cache

import json
import geopandas as gpd

# ---------------------------------------------------------------------------
# Comuni list
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_list_comuni(mapping_comuni_file: Path) -> list[dict]:
    """
    Return the list of all comuni. Cached for the process lifetime —
    the JSON mapping never changes while the server is running.
    """
    comuni = [{"code": "-1", "name": "Regione"}]
    with open(mapping_comuni_file, mode="r", encoding="utf-8") as fh:
        mapping = json.load(fh)
    for name, id_comune in mapping.items():
        comuni.append({"code": str(id_comune).zfill(6), "name": name})
    return comuni


# ---------------------------------------------------------------------------
# Comuni - areas mapping
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_macro_areas(codici_comuni_file: Path) -> list[any]:
    """
    Read a JSON file mapping macro-area names to lists of comune IDs.

    Returns a list of MacroArea objects.

    Result is cached for the process lifetime.
    """
    from .models.territorial_config import MacroArea

    with open(codici_comuni_file, "r", encoding="utf-8") as fh:
        data: dict[str, list[str]] = json.load(fh)

    for name, comuni in data.items():
        if not isinstance(comuni, list):
            raise TypeError(
                f"Expected list for {name!r}, got {type(comuni)}: {comuni!r}"
            )

    return [
        MacroArea(
            name=name,
            comuni=[str(c).zfill(6) for c in comuni],
        )
        for name, comuni in data.items()
        if comuni
    ]


# ---------------------------------------------------------------------------
# Map geometry
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_map_geometry_cached(map_shapefile: Path) -> gpd.GeoDataFrame:
    """
    Read and reproject the shapefile once.  Reprojection is expensive CPU
    work; doing it on every request was the dominant cost for map endpoints.
    """
    print(map_shapefile)

    gdf = gpd.read_file(map_shapefile).to_crs(epsg=4326)
    return gdf[gdf.COD_PROV == 22]


def get_map_geometry(map_shapefile: Path):
    """
    Return a copy of the cached geometry so callers that mutate the frame
    (e.g. _empty_map_response) don't corrupt the shared cache object.
    """
    return _load_map_geometry_cached(map_shapefile).copy()


# ---------------------------------------------------------------------------
# Macro-area geometry cache
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_macro_area_geometries_cached(
    codici_comuni_file: Path, geometry_file: Path
) -> gpd.GeoDataFrame:
    """
    Pre-compute the unioned polygon for each of the four province-level
    macro-areas.  Expensive (shapely union_all), so done once and cached.

    Returns a GeoDataFrame with columns [area_name, geometry].
    """

    gdf_base = _load_map_geometry_cached(geometry_file)
    rows = []
    for area in get_macro_areas(codici_comuni_file):
        mask = gdf_base["PRO_COM_T"].isin(area.comuni)
        geoms = gdf_base.loc[mask, "geometry"]
        if geoms.empty:
            continue
        union_geom = geoms.union_all()
        rows.append({"area_name": area.name, "geometry": union_geom})

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf_base.crs)


# ---------------------------------------------------------------------------
# Map response helpers
# ---------------------------------------------------------------------------


def _build_macro_area_geodataframe(
    result, codici_comuni_file: Path, geometry_file: Path
) -> gpd.GeoDataFrame:
    gdf_areas = (
        _build_macro_area_geometries_cached(codici_comuni_file, geometry_file)
        .rename(columns={"area_name": "AREA_NAME"})
        .copy()
    )

    merged = gdf_areas.merge(
        result.rename(columns={"ID_COMUNE": "AREA_NAME"}),
        on="AREA_NAME",
        how="left",
    )

    return gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf_areas.crs)
