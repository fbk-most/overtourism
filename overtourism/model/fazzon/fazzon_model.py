"""Fazzon (Lago dei Caprioli, Val di Sole) overtourism model definition.

The model uses the ``@define`` / ``compute()`` contract throughout — no
``legacy=True`` escape hatches.  Each concern sub-model declares its I/O
contract via ``@inputs`` / ``@outputs`` dataclasses and implements a single
``compute()`` method.  The root :class:`FazzonModel` wires all sub-models
inside its own ``compute()`` and exposes scenario-accessible indexes as
plain attributes set there.

Sub-models:

:class:`ParkingModel`
    Simultaneous car occupancy vs. policy cap (≈ 150 simultaneous spaces).

:class:`RoadModel`
    Daily vehicle passages (cars + shuttle buses) vs. effective road capacity
    under semaphore control.  Computes a **road cascade factor** (in [0, 1])
    and exposes it via ``Outputs.cascade_road`` for downstream sub-models.

:class:`FoodModel`
    Peak simultaneous diners (after road cascade) vs. total seat capacity
    (4 venues, 520 seats).  Takes ``cascade_road`` from :class:`RoadModel`.

:class:`LakesideModel`
    Simultaneous lakeside persons (after road cascade) vs. an environmental
    capacity threshold.  **ASSUMPTION** — no confirmed threshold from domain
    experts (Open Question 13 in fazzon-analysis.md).  Takes ``cascade_road``
    from :class:`RoadModel`.

:class:`FazzonModel`
    Root model — owns two CVs, two PVs, all ``i_*`` defaults, and wires the
    four sub-models.  Call :meth:`FazzonModel.default_inputs` to obtain a
    ready-to-use :class:`~FazzonModel.Inputs` instance.

Context variables
-----------------
cv_season   : june / july / august / september   (from 2025 parking data)
cv_day_type : peak / base                        (prior: 2/7 – 5/7)

Presence variables
------------------
pv_visitors_car   : daily car-mode visitors (calibrated; 2025 parking data)
pv_visitors_other : daily non-car visitors  (ASSUMPTION; EETRA 2022 survey)

NOTE: weather CV is omitted — no weather labels exist in any Fazzon dataset.
"""

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass

from scipy import stats

from civic_digital_twins.dt_model import (
    CategoricalIndex,
    ConditionalDistributionIndex,
    DistributionIndex,
    GenericIndex,
    Index,
    Model,
    define,
    graph,
    inputs,
    outputs,
)

from .fazzon_presence_stats import (
    car_visitors_stats,
    day_type,
    other_visitors_stats,
    season,
)


# ---------------------------------------------------------------------------
# Constraint
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Constraint:
    """Named pairing of a usage formula index and a capacity index."""

    name: str
    usage: Index
    capacity: Index


# ---------------------------------------------------------------------------
# ParkingModel
# ---------------------------------------------------------------------------


@define("Parking")
class ParkingModel(Model):
    """Concern sub-model — simultaneous parking occupancy.

    Converts daily car-mode visitor count to a simultaneous occupancy estimate
    using the observed occupancy ratio (dwell_time / operating_window = 0.555),
    then compares against the policy cap.

    Formula::

        pv_cars = pv_visitors_car / i_xa_persons_per_car
        i_u_parking = pv_cars * i_occupancy_ratio
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`ParkingModel`."""

        pv_visitors_car: ConditionalDistributionIndex
        i_xa_persons_per_car: Index
        i_occupancy_ratio: Index
        i_c_parking: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`ParkingModel`."""

        i_u_parking: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute simultaneous parking occupancy from daily car-mode visitors."""
        i_u_parking = Index(
            "parking usage",
            inputs.pv_visitors_car / inputs.i_xa_persons_per_car * inputs.i_occupancy_ratio,
        )
        self.constraint = Constraint(name="parking", usage=i_u_parking, capacity=inputs.i_c_parking)
        return ParkingModel.Outputs(i_u_parking=i_u_parking)


# ---------------------------------------------------------------------------
# RoadModel
# ---------------------------------------------------------------------------


@define("Road")
class RoadModel(Model):
    """Concern sub-model — daily vehicle passages on the Fazzon access road.

    The access road (4.3 km, single-lane with semaphore under shuttle
    operation) carries both private cars and shuttle buses.  The daily vehicle
    passage count is compared to an effective road capacity.

    A **road cascade factor** is computed here and exposed via
    ``Outputs.cascade_road`` for downstream use in :class:`FoodModel` and
    :class:`LakesideModel`::

        cascade_road = min(1, i_c_road / i_u_road)

    When the road is not saturated the factor is 1.0; when saturated it
    represents the fraction of intended visitors that can physically reach
    the lake.

    Formula::

        road_veh_cars = (pv_visitors_car + pv_visitors_other)
                        * i_car_mode_share / i_xa_persons_per_car
                        * i_xo_road_trips
        i_u_road = road_veh_cars + i_shuttle_daily_trips
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`RoadModel`."""

        pv_visitors_car: ConditionalDistributionIndex
        pv_visitors_other: ConditionalDistributionIndex
        i_car_mode_share: Index
        i_xa_persons_per_car: Index
        i_xo_road_trips: Index
        i_shuttle_daily_trips: Index
        i_c_road: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`RoadModel`."""

        i_u_road: Index
        cascade_road: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute road vehicle demand, cascade factor, and road constraint."""
        _road_vehicle_demand = (
            (inputs.pv_visitors_car + inputs.pv_visitors_other)
            * inputs.i_car_mode_share
            / inputs.i_xa_persons_per_car
            * inputs.i_xo_road_trips
            + inputs.i_shuttle_daily_trips
        )
        i_u_road = Index("road usage", _road_vehicle_demand)

        # Cascade: fraction of visitors reaching the lake when road is saturated.
        # 1e-10 guard: piecewise evaluates all branches eagerly in numpy; the
        # ratio branch is only used when demand > capacity (> 0), so the
        # denominator epsilon only matters at demand≈0 where the condition
        # is False anyway — it prevents a RuntimeWarning there.
        cascade_road = Index(
            "road cascade factor",
            graph.piecewise(
                (inputs.i_c_road / (_road_vehicle_demand + 1e-10), _road_vehicle_demand > inputs.i_c_road),
                (1.0, True),
            ),
        )

        self.constraint = Constraint(name="road", usage=i_u_road, capacity=inputs.i_c_road)
        return RoadModel.Outputs(i_u_road=i_u_road, cascade_road=cascade_road)


# ---------------------------------------------------------------------------
# FoodModel
# ---------------------------------------------------------------------------


@define("Food")
class FoodModel(Model):
    """Concern sub-model — daily restaurant demand at the 4 lake venues.

    Models peak simultaneous diners as a fraction of visitors reaching the
    lake (after road cascade), divided by the daily seat turnover.  The
    constraint is peak simultaneous demand ≤ total seats (520).

    Formula::

        pv_visitors_at_lake = (pv_visitors_car + pv_visitors_other) * cascade_road
        i_u_food = pv_visitors_at_lake * i_u_food_fraction / i_xo_food_sittings
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`FoodModel`."""

        pv_visitors_car: ConditionalDistributionIndex
        pv_visitors_other: ConditionalDistributionIndex
        cascade_road: Index
        i_u_food_fraction: Index
        i_xo_food_sittings: Index
        i_c_seats: Index

    @outputs
    class Outputs:
        """Contractual outputs of :class:`FoodModel`."""

        i_u_food: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute peak simultaneous diners after road cascade."""
        pv_visitors_at_lake = (inputs.pv_visitors_car + inputs.pv_visitors_other) * inputs.cascade_road
        i_u_food = Index(
            "food usage",
            pv_visitors_at_lake * inputs.i_u_food_fraction / inputs.i_xo_food_sittings,
        )
        self.constraint = Constraint(name="food", usage=i_u_food, capacity=inputs.i_c_seats)
        return FoodModel.Outputs(i_u_food=i_u_food)


# ---------------------------------------------------------------------------
# LakesideModel
# ---------------------------------------------------------------------------


@define("Lakeside")
class LakesideModel(Model):
    """Concern sub-model — simultaneous persons at the lakeshore.

    Estimates peak simultaneous lakeside occupancy using a dwell fraction
    analogous to the parking occupancy ratio.  The capacity threshold is an
    **ASSUMPTION** — no confirmed threshold from domain experts (Open
    Question 13 in fazzon-analysis.md); must be validated with ASUC and
    environmental managers.

    Formula::

        pv_visitors_at_lake = (pv_visitors_car + pv_visitors_other) * cascade_road
        i_u_lakeside = pv_visitors_at_lake * i_dwell_fraction
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`LakesideModel`."""

        pv_visitors_car: ConditionalDistributionIndex
        pv_visitors_other: ConditionalDistributionIndex
        cascade_road: Index
        i_dwell_fraction: Index
        i_c_lakeside: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`LakesideModel`."""

        i_u_lakeside: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute peak simultaneous lakeside occupancy after road cascade."""
        pv_visitors_at_lake = (inputs.pv_visitors_car + inputs.pv_visitors_other) * inputs.cascade_road
        i_u_lakeside = Index(
            "lakeside usage",
            pv_visitors_at_lake * inputs.i_dwell_fraction,
        )
        self.constraint = Constraint(name="lakeside", usage=i_u_lakeside, capacity=inputs.i_c_lakeside)
        return LakesideModel.Outputs(i_u_lakeside=i_u_lakeside)


# ---------------------------------------------------------------------------
# FazzonModel
# ---------------------------------------------------------------------------


@define("Fazzon")
class FazzonModel(Model):
    """Root overtourism model for Fazzon — wires the four concern sub-models.

    Instantiate via :meth:`default_inputs`::

        model = FazzonModel(inputs=FazzonModel.default_inputs())

    Callers can override any parameter via :class:`~dt_model.Scenario`
    overrides targeting the scalar indexes exposed as instance attributes
    (e.g. ``model.i_c_parking``, ``model.i_shuttle_daily_trips``).  These
    attributes are aliased from ``model.inputs.*`` inside ``compute()`` and
    refer to the same index object, so scenario overrides work identically
    whether you target ``model.i_c_parking`` or ``model.inputs.i_c_parking``.

    Context variables
    -----------------
    cv_season   : june / july / august / september   (prior: proportional to observed days)
    cv_day_type : peak / base                        (prior: 2/7 – 5/7)

    Presence variables
    ------------------
    pv_visitors_car   : daily car-mode visitors (axis x on the sustainability field)
    pv_visitors_other : daily non-car visitors  (axis y on the sustainability field)

    All ASSUMPTION-tagged values should be validated with ASUC, PAT mobility
    data, and environmental managers of the Lago dei Caprioli reserve.
    """

    @inputs
    class Inputs:
        """All domain parameters of :class:`FazzonModel`."""

        # Context variables
        cv_season: CategoricalIndex
        cv_day_type: CategoricalIndex
        # Presence distributions
        pv_visitors_car: ConditionalDistributionIndex
        pv_visitors_other: ConditionalDistributionIndex
        # Conversion parameters
        i_xa_persons_per_car: Index
        i_occupancy_ratio: Index
        i_xo_road_trips: Index
        i_car_mode_share: Index
        # Shuttle
        i_shuttle_daily_trips: Index
        # Dwell and food parameters
        i_dwell_fraction: Index
        i_u_food_fraction: Index
        i_xo_food_sittings: Index
        # Capacity parameters
        i_c_parking: DistributionIndex
        i_c_road: DistributionIndex
        i_c_seats: Index
        i_c_lakeside: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`FazzonModel`."""

        usage_indexes: list[GenericIndex]

    @classmethod
    def default_inputs(cls) -> "FazzonModel.Inputs":
        """Return default domain inputs for the 2025 regulated season.

        All defaults are calibrated from 2025 Fazzon parking ticket data and
        the 2022 EETRA modal-split survey.  Values marked ASSUMPTION have not
        been confirmed by domain experts.

        Override individual fields with :func:`dataclasses.replace` or supply
        a :class:`~dt_model.Scenario` at evaluation time.
        """
        cv_season = CategoricalIndex("season", {s: season[s] for s in season})
        cv_day_type = CategoricalIndex("day_type", {d: day_type[d] for d in day_type})

        pv_visitors_car = ConditionalDistributionIndex(
            "visitors_car",
            [cv_day_type, cv_season],
            car_visitors_stats,
        )
        pv_visitors_other = ConditionalDistributionIndex(
            "visitors_other",
            [cv_day_type, cv_season],
            other_visitors_stats,
        )

        return cls.Inputs(
            cv_season=cv_season,
            cv_day_type=cv_day_type,
            pv_visitors_car=pv_visitors_car,
            pv_visitors_other=pv_visitors_other,
            # Conversion parameters
            i_xa_persons_per_car=Index("persons per car", 2.83),  # NetMobility 2021
            i_occupancy_ratio=Index("parking occupancy ratio", 0.555),  # 4.44h/8h, 2021 calibration
            i_xo_road_trips=Index("road round-trip multiplier", 2.0),  # in + out = 2 passages
            i_car_mode_share=Index("car mode share", 0.69),  # ASSUMPTION: 2022 EETRA; scenario-overridable
            # Shuttle
            i_shuttle_daily_trips=Index("shuttle daily vehicle passages", 0.0),
            # NOTE: 0 = no shuttle (2025 baseline; shuttle data for 2025 contaminated).
            # Override in scenarios: 32 = 2 buses × 8 A/R trips × 2 directions.
            # Dwell and food
            i_dwell_fraction=Index("visitor dwell fraction", 0.555),  # 4.4h/8h, ASSUMPTION proxy
            i_u_food_fraction=Index("restaurant usage fraction", 0.55),  # ASSUMPTION: >50% (EETRA 2022)
            i_xo_food_sittings=Index("food seat turnover", 2.0),  # ASSUMPTION: ~2 sittings/seat/day
            # Capacities
            # Parking: policy cap is 150 simultaneous cars.  Triangular captures
            # uncertainty about whitelist slots (30 reserved), enforcement, and
            # peak-hour variability.  Mode=200 = physical upper bound.
            i_c_parking=DistributionIndex(
                "parking capacity (simultaneous cars)",
                stats.triang,
                {"loc": 150.0, "scale": 100.0, "c": 0.5},  # mode=200, range [150, 250]
            ),
            # Road: effective daily vehicle capacity under semaphore control.
            # Peak observed 2025: 422 cars × 2 trips = 844 passages; road not saturated.
            i_c_road=DistributionIndex(
                "road capacity (vehicle passages/day)",
                stats.uniform,
                {"loc": 800.0, "scale": 600.0},  # ASSUMPTION uniform[800, 1400] veh passages/day
            ),
            # Restaurant seats: 4 venues, 520 total (from data — no uncertainty).
            i_c_seats=Index("restaurant seats", 520.0),
            # Lakeside — ASSUMPTION: no confirmed threshold from domain experts
            # (Open Question 13 in fazzon-analysis.md).  Range [400, 800] spans
            # a conservative experiential limit to a plausible maximum given the
            # shoreline area.  MUST be validated with ASUC and environmental managers.
            i_c_lakeside=DistributionIndex(
                "lakeside capacity (simultaneous persons)",
                stats.uniform,
                {"loc": 400.0, "scale": 400.0},  # ASSUMPTION uniform[400, 800] persons
            ),
        )

    def compute(self, inputs: Inputs) -> Outputs:
        """Wire the four concern sub-models from flat inputs."""
        parking = ParkingModel(
            inputs=ParkingModel.Inputs(
                pv_visitors_car=inputs.pv_visitors_car,
                i_xa_persons_per_car=inputs.i_xa_persons_per_car,
                i_occupancy_ratio=inputs.i_occupancy_ratio,
                i_c_parking=inputs.i_c_parking,
            )
        )
        road = RoadModel(
            inputs=RoadModel.Inputs(
                pv_visitors_car=inputs.pv_visitors_car,
                pv_visitors_other=inputs.pv_visitors_other,
                i_car_mode_share=inputs.i_car_mode_share,
                i_xa_persons_per_car=inputs.i_xa_persons_per_car,
                i_xo_road_trips=inputs.i_xo_road_trips,
                i_shuttle_daily_trips=inputs.i_shuttle_daily_trips,
                i_c_road=inputs.i_c_road,
            )
        )
        food = FoodModel(
            inputs=FoodModel.Inputs(
                pv_visitors_car=inputs.pv_visitors_car,
                pv_visitors_other=inputs.pv_visitors_other,
                cascade_road=road.outputs.cascade_road,
                i_u_food_fraction=inputs.i_u_food_fraction,
                i_xo_food_sittings=inputs.i_xo_food_sittings,
                i_c_seats=inputs.i_c_seats,
            )
        )
        lakeside = LakesideModel(
            inputs=LakesideModel.Inputs(
                pv_visitors_car=inputs.pv_visitors_car,
                pv_visitors_other=inputs.pv_visitors_other,
                cascade_road=road.outputs.cascade_road,
                i_dwell_fraction=inputs.i_dwell_fraction,
                i_c_lakeside=inputs.i_c_lakeside,
            )
        )

        self.constraints = [
            parking.constraint,
            road.constraint,
            food.constraint,
            lakeside.constraint,
        ]

        # Expose scenario-accessible indexes as direct attributes.
        # These are identity-aliases of the corresponding inputs fields:
        # scenario overrides work identically on either name.
        self.i_c_parking = inputs.i_c_parking
        self.i_c_road = inputs.i_c_road
        self.i_c_seats = inputs.i_c_seats
        self.i_c_lakeside = inputs.i_c_lakeside
        self.i_car_mode_share = inputs.i_car_mode_share
        self.i_shuttle_daily_trips = inputs.i_shuttle_daily_trips
        # Cascade factor is computed inside RoadModel; expose for inspection.
        self.i_cascade_road = road.outputs.cascade_road

        return FazzonModel.Outputs(usage_indexes=[c.usage for c in self.constraints])

