from overtourism.overtourism.backend_extension.api.models.phenomenon import Phenomenon

# ---------------------------------------------------------------------------
# Italian translations for phenomenon keywords returned in API responses
# ---------------------------------------------------------------------------
# The GeoJSON properties returned by /get_index_data carry one column per
# phenomenon that makes up the requested indicator (e.g. "beds" and
# "population" for "tasso-ricettivita"), plus "INDICE" itself. Those column
# names come straight from each Phenomenon's `.name` (see the phenomenon
# classes below) and are English by convention, since they're also used
# internally as pandas/DataFrame keys throughout indicator.py.
#
# This dictionary is the single predefined mapping from those internal
# keywords to the Italian labels exposed to the frontend. It's applied via
# `index_utils._translate_columns()` right before a GeoDataFrame is
# serialised to GeoJSON, so indicator/phenomenon internals never need to
# know about it.
#
# Only keys listed here get renamed — "AREA_NAME", "INDICE", and "geometry"
# are intentionally left out and pass through unchanged. Add an entry here
# whenever a new Phenomenon (or a custom `name=...` override) is introduced
# and should be human-readable in the API response.

PHENOMENON_LABELS_IT: dict[str, str] = {
    # AccommodationCapacityIndicator ("tasso-ricettivita")
    "beds": "posti letto",
    "population": "popolazione",
    # TourismIndexIndicator ("indice-turisticita")
    "presences": "presenze",
    # HospitalityIndexFacilitiesIndicator ("indice-ospitalita-strutture")
    "extra_Facilities": "strutture extra-alb.",
    "Facilities_total": "strutture totali",
    # HospitalityIndexBedsIndicator ("indice-ospitalita-letti")
    "extra_beds": "posti letto extra-alb.",
    # HiddenTourismIndicator ("indice-turismo-sommerso")
    "presenze_vodafone": "presenze rete mobile",
    "presenze_alb": "presenze alb.",
    "presenze_xalb": "presenze extra-alb.",
    # FlowPhenomenon-based indicators (RatioFlowsIndicator, FlowsIndicatorLevel;
    # currently only reachable if INCLUDE_TEMP_REGISTRY is enabled)
    "flows": "flussi",
    "flow_value": "valore flusso",
}

# ---------------------------------------------------------------------------
# Concrete phenomena
# ---------------------------------------------------------------------------


class PresencesPhenomenon(Phenomenon):
    """Total presences (tourists, excursionists, or combined)."""

    name = "presences"
    # Native resolution: daily × comune  →  both axes are 'identity'
    temporal_resolution = "daily"
    temporal_strategy = "identity"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="presenze", name=None):
        super().__init__(source, col, agg="mean")
        if name is not None:
            self.name = name


class BedsPhenomenon(Phenomenon):
    """Total beds (all accommodation types)."""

    name = "beds"
    # Beds don't change day-to-day within a period; treat as constant daily.
    # If the source is already daily, temporal_strategy='identity' is fine too.
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_postiletto"):
        super().__init__(source, col, agg="mean")


class ExtraBedsPhenomenon(Phenomenon):
    """Beds in non-hotel (extra-alberghiero) facilities."""

    name = "extra_beds"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_postiletto_non_conv"):
        super().__init__(source, col, agg="mean")


class FacilitiesTotalPhenomenon(Phenomenon):
    """Total accommodation facilities."""

    name = "Facilities_total"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_strutture"):
        super().__init__(source, col, agg="mean")


class ExtraFacilitiesPhenomenon(Phenomenon):
    """Non-hotel facilities."""

    name = "extra_Facilities"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="tot_strutture_non_conv"):
        super().__init__(source, col, agg="mean")


class PopulationPhenomenon(Phenomenon):
    """
    Resident population.
    """

    name = "population"
    temporal_resolution = "yearly"
    temporal_strategy = "constant"  # broadcast uniformly across days
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(self, source, col="popolazione"):
        super().__init__(
            source,
            col,
            agg="mean",
            dtype={"LOCATION_ID": str},
        )


# ---------------------------------------------------------------------------
# Temporary phenomena
# ---------------------------------------------------------------------------


class FlowPhenomenon(Phenomenon):
    """Flows in/out + users"""

    name = "flows"
    temporal_strategy = "constant"
    temporal_resolution = "yearly"
    spatial_resolution = "comune"
    spatial_strategy = "identity"

    def __init__(
        self, source, col="flows", municipality_id_col="ID", name=None, agg="mean"
    ):  # TODO: check why mean works and not sum
        super().__init__(
            source,
            col,
            agg=agg,
            municipality_id_col=municipality_id_col,
        )
        if name is not None:
            self.name = name


# class ArrivalsPhenomenon(Phenomenon):
#     """Total arrivals."""

#     name = "arrivals"
#     temporal_resolution = "daily"
#     temporal_strategy = "identity"
#     spatial_resolution = "comune"
#     spatial_strategy = "identity"

#     def __init__(self, source, col="NUMARRIVATI_TOT"):
#         super().__init__(source, col, agg="sum")
