"""API endpoints for data analysis functions."""

import logging
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, Depends

from datetime import datetime
from typing import Optional, Dict, Any
from time import time

from overtourism.backend.api.v2.models.territorial_config import TerritorialConfig
from overtourism.backend.api.v2.index_utils import (
    _empty_map_response,
    _build_geodataframe,
    _to_map_response,
    get_chart_labels,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.backend.api.v2.models.trentino_indicators import (
    _REGISTRY,
    CODICI_COMUNI_FILE,
    MACRO_AREAS_FILE,
    MAP_SHAPEFILE,
    get_indicator,
)
from overtourism.backend.api.v2.index_utils_trentino import (
    get_list_comuni,
    get_macro_areas,
    get_map_geometry,
    _build_macro_area_geodataframe,
)

logger = logging.getLogger(__name__)

indexes_router = APIRouter(
    prefix=f"{TENANT_ROUTE_PREFIX}/indexes",
    tags=["Indexes"],
    # TODO: restoredependencies=[Depends(get_auth_context)],
)

# ---------------------------------------------------------------------------
# Endpoint-level permission defaults
# Future: replace with per-user resolution from auth token / session.
# ---------------------------------------------------------------------------

# None = all comuni are visible (maximum permission).
_DEFAULT_ALLOWED_COMUNI: Optional[set[str]] = None

# ---------------------------------------------------------------------------
# Shared param: the only territorial input accepted from the frontend
# ---------------------------------------------------------------------------

# Extra query params that are never forwarded to indicator combinators
_KNOWN_PARAMS = {
    "index",
    "start_date",
    "end_date",
    "start_date_baseline",
    "end_date_baseline",
    "start_date_comparison",
    "end_date_comparison",
    "granularity",  # temporal granularity for charts
    "spatial_granularity",  # territorial granularity (frontend)
}


def _build_tc(
    request: Request,
    *,
    allowed_comuni: Optional[set[str]] = _DEFAULT_ALLOWED_COMUNI,
    macro_area_agg: str = "mean",
) -> TerritorialConfig:
    """
    Build a TerritorialConfig for a request.

    ``spatial_granularity`` is the only territorial parameter read from the
    query string.  Everything else is server-controlled.

    Parameters
    ----------
    request
        FastAPI request object.
    allowed_comuni
        Hardcoded per endpoint.  ``None`` = all comuni allowed.
    macro_area_agg
        "mean" for ratio/index indicators, "sum" for count indicators.
        Hardcoded per endpoint (or overridable in the future).
    """
    spatial_granularity = request.query_params.get("spatial_granularity", "comune")
    try:
        return TerritorialConfig.build(
            areas=get_macro_areas(MACRO_AREAS_FILE),
            spatial_granularity=spatial_granularity,
            allowed_comuni=allowed_comuni,
            macro_area_agg=macro_area_agg,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _extra_params(request: Request) -> dict:
    """Strip all known/territorial params; return indicator-specific extras."""
    return {k: v for k, v in request.query_params.items() if k not in _KNOWN_PARAMS}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@indexes_router.get("/get-index-list", response_model=Dict[str, Any])
def get_indicators_list():
    """
    Get list of all available indices.

    Returns:
        Dictionary with the list of indicators, ready to populate the
        frontend's indicator dropdown (value, label, availableForVariation,
        extraFields).
    """
    logger.info("[get-index-list] Fetching list of indices")
    try:
        indicators = []
        for key in _REGISTRY:
            indicator = get_indicator(key)
            indicators.append(
                {
                    "value": key,
                    "label": indicator.name or key,
                    "availableForVariation": indicator.availableForVariation,
                    "extraFields": indicator.extraFields,
                    "years_range": {
                        "min_year": indicator.years_range["min_year"],
                        "max_year": indicator.years_range["max_year"],
                    },
                }
            )
        return {"indicators": indicators}
    except Exception as e:
        logger.info(f"[get-index-list] Error fetching indicators: {e}")
        raise HTTPException(
            status_code=500, detail="Error fetching indicators list"
        ) from e


@indexes_router.get("/get-comuni", response_model=Dict[str, Any])
def get_comuni(request: Request):
    """
    Return the list of spatial units visible to the caller.

    At "comune" granularity: the filtered list of individual comuni.
    At "macro_area" granularity: the four province-level area names.

    The region aggregate ("-1") is always included first.
    """
    logger.info("[get-comuni] Fetching list of comuni")
    try:
        tc = _build_tc(request)

        if tc.spatial_granularity == "macro_area":
            area_entries = [{"code": a.name, "name": a.name} for a in tc.areas]
            return {"comuni": [{"code": "-1", "name": "Regione"}] + area_entries}

        # Comune granularity: filter by allowed_comuni
        all_comuni = get_list_comuni(CODICI_COMUNI_FILE)
        if tc.allowed_comuni is not None:
            comuni = [
                c
                for c in all_comuni
                if c["code"] == "-1" or c["code"] in tc.allowed_comuni
            ]
        else:
            comuni = all_comuni

        return {"comuni": comuni}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@indexes_router.get("/get_index_data", response_model=Dict[str, Any])
def get_index_data(
    request: Request,
    index: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    try:
        t1 = time()
        tc = _build_tc(request)
        indicator = get_indicator(index)
        extra = _extra_params(request)

        logger.info(
            f"[{index}] start_date={start_date}, end_date={end_date}, "
            f"extra={extra}, spatial_granularity={tc.spatial_granularity}"
        )

        gdf_base = get_map_geometry(MAP_SHAPEFILE)

        computed_index = indicator.get_indicator(
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

        if computed_index is None:
            geo_data = _empty_map_response(gdf_base)
        else:
            result = tc.apply(computed_index)
            if tc.spatial_granularity == "macro_area":
                gdf_final = _build_macro_area_geodataframe(
                    result, MACRO_AREAS_FILE, MAP_SHAPEFILE
                )
            else:
                gdf_final = _build_geodataframe(gdf_base, result)
            geo_data = _to_map_response(gdf_final)

        return {
            "geo_data": {
                "data": geo_data["geojson"],
                "min_value": geo_data["min_value"],
                "max_value": geo_data["max_value"],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@indexes_router.get("/get-variation-data", response_model=Dict[str, Any])
def get_variation_data(
    request: Request,
    index: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    granularity: Optional[str] = Query(None),
):
    """
    Time-series variation for the region and selected comuni / macro-areas.

    ``granularity`` here is *temporal* (giornaliero / mensile / annuale).
    ``spatial_granularity`` (query param) controls the territorial grain.
    """
    try:
        t1 = time()
        tc = _build_tc(request)
        logger.info(
            f"[{index} variation] start_date={start_date}, end_date={end_date}, "
            f"temporal={granularity}, spatial={tc.spatial_granularity}"
        )

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        labels = get_chart_labels(start_dt, end_dt, granularity)
        indicator = get_indicator(index)
        raw_series = indicator.get_temporal_variation(
            start_date=start_dt,
            end_date=end_dt,
            granularity=granularity,
        )

        series = tc.apply_to_series(raw_series)

        return {"labels": labels, "series": series}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))


@indexes_router.get("/get-variation-over-time", response_model=Dict[str, Any])
def get_variation_over_time(
    request: Request,
    index: str,
    start_date_baseline: Optional[str] = Query(None),
    end_date_baseline: Optional[str] = Query(None),
    start_date_comparison: Optional[str] = Query(None),
    end_date_comparison: Optional[str] = Query(None),
):
    """
    Percentage change of an indicator between two periods, mapped per comune
    or per macro-area depending on ``spatial_granularity``.
    """
    try:
        t1 = time()
        tc = _build_tc(request)
        indicator = get_indicator(index)
        extra = _extra_params(request)

        logger.info(
            f"[{index} variation-over-time] "
            f"baseline=({start_date_baseline}, {end_date_baseline}) "
            f"comparison=({start_date_comparison}, {end_date_comparison}) "
            f"extra={extra}, spatial={tc.spatial_granularity}"
        )

        gdf_base = get_map_geometry(MAP_SHAPEFILE)
        baseline_df = indicator.get_indicator(
            start_date=start_date_baseline,
            end_date=end_date_baseline,
            **extra,
        )
        current_df = indicator.get_indicator(
            start_date=start_date_comparison,
            end_date=end_date_comparison,
            **extra,
        )

        if baseline_df is None or current_df is None:
            geo_data = _empty_map_response(gdf_base)
        else:
            merged = baseline_df[["ID_COMUNE", "INDICE"]].merge(
                current_df[["ID_COMUNE", "INDICE"]],
                on="ID_COMUNE",
                how="outer",
                suffixes=("_baseline", "_comparison"),
            )
            merged["INDICE"] = (
                (merged["INDICE_comparison"] - merged["INDICE_baseline"])
                / merged["INDICE_baseline"].replace(0, np.nan)
            ) * 100

            result = tc.apply(merged[["ID_COMUNE", "INDICE"]])

            if tc.spatial_granularity == "macro_area":
                gdf_final = _build_macro_area_geodataframe(
                    result, MACRO_AREAS_FILE, MAP_SHAPEFILE
                )
            else:
                gdf_final = _build_geodataframe(gdf_base, result)
            geo_data = _to_map_response(gdf_final)

        return {
            "geo_data": {
                "data": geo_data["geojson"],
                "min_value": geo_data["min_value"],
                "max_value": geo_data["max_value"],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
