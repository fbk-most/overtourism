"""API endpoints for data analysis functions."""

import logging
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, Depends

from datetime import datetime
from typing import Optional, Dict, Any
from time import time

from overtourism.overtourism.backend_extension.models.territorial_config import (
    TerritorialConfig,
)
from overtourism.backend.api.v2.index_utils import (
    _build_geodataframe,
    _to_map_response,
    get_chart_labels,
)
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.api.v2.config import TENANT_ROUTE_PREFIX
from overtourism.overtourism.backend_extension.models.trentino_indicators import (
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
    dependencies=[Depends(get_auth_context)],
)

# from pathlib import Path
# PATH_JSON_MAP = Path(__file__).parent.resolve() / 'filename.json'

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
# Date validation helpers
# ---------------------------------------------------------------------------


def _parse_date(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse a YYYY-MM-DD date string, raising a 422 on bad input."""
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format for '{field_name}': {value!r}. "
            "Expected YYYY-MM-DD.",
        ) from exc


def _validate_date_order(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    start_field: str = "start_date",
    end_field: str = "end_date",
) -> None:
    """Ensure end_dt is not before start_dt (when both are present)."""
    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        raise HTTPException(
            status_code=422,
            detail=f"'{end_field}' ({end_dt.date()}) cannot be before "
            f"'{start_field}' ({start_dt.date()}).",
        )


# ---------------------------------------------------------------------------
# Map value validation helper
# ---------------------------------------------------------------------------


def _validate_map_values(min_value: Any, max_value: Any, *, context: str) -> None:
    """
    Guard against degenerate / invalid map value ranges.

    Raises instead of letting the response go out when:
      - both min_value and max_value are <= 0, or
      - either min_value or max_value is NaN.
    """
    min_is_nan = min_value is None or (
        isinstance(min_value, float) and np.isnan(min_value)
    )
    max_is_nan = max_value is None or (
        isinstance(max_value, float) and np.isnan(max_value)
    )

    if min_is_nan or max_is_nan:
        raise HTTPException(
            status_code=422,
            detail=f"[{context}] Computed value range is invalid "
            f"(min_value={min_value}, max_value={max_value}).",
        )

    if min_value <= 0 and max_value <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"[{context}] Computed value range is non-positive "
            f"(min_value={min_value}, max_value={max_value}).",
        )


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
            if not indicator.internal_only:
                indicators.append(
                    {
                        "value": key,
                        "label": indicator.name or key,
                        "index_description": indicator.description,
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


def _extra_params(request: Request, indicator) -> dict:
    """
    Return only the query params this specific indicator has declared it
    needs, via its `extraFields` class attribute. "seasonality" is always
    allowed since the base Indicator._compute_indicator() supports it
    for every indicator, not just ones that list it explicitly.
    """
    allowed = set(getattr(indicator, "extraFields", ())) | {"seasonality"}
    return {k: v for k, v in request.query_params.items() if k in allowed}


@indexes_router.get("/get_index_data", response_model=Dict[str, Any])
def get_index_data(
    request: Request,
    index: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    try:
        tc = _build_tc(request)
        indicator = get_indicator(index)
        extra = _extra_params(
            request, indicator
        )  # <-- whitelist driven by this indicator

        logger.info(
            f"[{index}] start_date={start_date}, end_date={end_date}, "
            f"extra={extra}, spatial_granularity={tc.spatial_granularity}"
        )

        start_dt = _parse_date(start_date, "start_date")
        end_dt = _parse_date(end_date, "end_date")
        _validate_date_order(start_dt, end_dt)

        gdf_base = get_map_geometry(MAP_SHAPEFILE)

        computed_index = indicator.get_indicator(
            start_date=start_date,
            end_date=end_date,
            **extra,
        )

        if computed_index is None:
            raise RuntimeError("It was not possible to compute the indicator")

        else:
            result = tc.apply(computed_index)
            if tc.spatial_granularity == "macro_area":
                gdf_final = _build_macro_area_geodataframe(
                    result, MACRO_AREAS_FILE, MAP_SHAPEFILE
                )
            # elif index.startswith(tuple(_VODAFONE_ID_PREFIXES)):
            #     gdf_final = _build_geodataframe_vodafone_ids(gdf_base, result)
            else:
                gdf_final = _build_geodataframe(gdf_base, result)
            geo_data = _to_map_response(gdf_final)

        _validate_map_values(
            geo_data["min_value"],
            geo_data["max_value"],
            context=f"{index} get_index_data",
        )

        return {
            "geo_data": {
                "data": geo_data["geojson"],
                "min_value": geo_data["min_value"],
                "max_value": geo_data["max_value"],
            },
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
        tc = _build_tc(request)
        logger.info(
            f"[{index} variation] start_date={start_date}, end_date={end_date}, "
            f"temporal={granularity}, spatial={tc.spatial_granularity}"
        )

        start_dt = _parse_date(start_date, "start_date")
        end_dt = _parse_date(end_date, "end_date")
        if start_dt is None or end_dt is None:
            raise HTTPException(
                status_code=422,
                detail="Both 'start_date' and 'end_date' are required.",
            )
        _validate_date_order(start_dt, end_dt)

        labels = get_chart_labels(start_dt, end_dt, granularity)
        indicator = get_indicator(index)
        raw_series = indicator.get_temporal_variation(
            start_date=start_dt,
            end_date=end_dt,
            granularity=granularity,
        )

        series = tc.apply_to_series(raw_series)

        return {
            "labels": labels,
            "series": series,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
