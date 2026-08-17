"""Molveno overtourism model definition — modular decomposition.

The model is split into four concern sub-models plus a root model.  Context
variables (``cv_*``) and presence variables (``pv_*``) are constructed
directly on the root :class:`MolvenoModel` and wired down to each concern
sub-model through its ``Inputs`` dataclass.

:class:`ParkingModel` — *Parking usage*
    **Inputs**: ``pv_tourists``, ``pv_excursionists``, ``cv_weather``,
    ``i_u_tourists_parking``, ``i_u_excursionists_parking``,
    ``i_xa_tourists_per_vehicle``, ``i_xa_excursionists_per_vehicle``,
    ``i_xo_tourists_parking``, ``i_xo_excursionists_parking``,
    ``i_c_parking``
    **Outputs**: ``i_u_parking``

:class:`BeachModel` — *Beach usage*
    **Inputs**: ``pv_tourists``, ``pv_excursionists``, ``cv_weather``,
    ``i_u_tourists_beach``, ``i_u_excursionists_beach``,
    ``i_xo_tourists_beach`` *(uncertain)*, ``i_xo_excursionists_beach``,
    ``i_c_beach``
    **Outputs**: ``i_u_beach``

:class:`AccommodationModel` — *Accommodation usage*
    **Inputs**: ``pv_tourists``,
    ``i_u_tourists_accommodation``, ``i_xa_tourists_accommodation``,
    ``i_c_accommodation``
    **Outputs**: ``i_u_accommodation``

:class:`FoodModel` — *Food-service usage*
    **Inputs**: ``pv_tourists``, ``pv_excursionists``, ``cv_weather``,
    ``i_u_tourists_food``, ``i_u_excursionists_food``,
    ``i_xa_visitors_food``, ``i_xo_visitors_food``, ``i_c_food``
    **Outputs**: ``i_u_food``

:class:`MolvenoModel` — *Root, owns CVs, PVs, and all* ``i_*`` *defaults*
    Creates the three context variables
    (:class:`~civic_digital_twins.dt_model.CategoricalIndex`), the two
    presence variables, and all ``i_*`` indexes with their default values,
    then passes them to the four concern sub-models.  Retains the domain
    attributes (``cvs``, ``pvs``, ``constraints``) required by
    :class:`~dt_model.CrossProductEnsemble`.

Design rules:

* **All** ``i_*`` parameters are ``Inputs`` to the sub-model that uses
  them, including uncertain ``DistributionIndex`` values.  The default
  values are created by :class:`MolvenoModel` and passed down via
  constructors.  A caller who wants to override a parameter simply
  supplies a different index object at construction time.
* Context variables (``cv_*``) and presence variables (``pv_*``) are
  attributes of :class:`MolvenoModel` and are wired as ``Inputs`` to the
  concern sub-models that consume them.
* Each concern sub-model's ``Outputs`` contains only the usage-formula
  index (``i_u_*``).  Capacity indexes (``i_c_*``) remain as ``Inputs``
  because they are parameters, not computed results.
* Each concern sub-model stores its
  :class:`~overtourism.model.molveno.molveno_model.Constraint` as a
  plain instance attribute (``self.constraint``) because
  :class:`~overtourism.model.molveno.molveno_model.Constraint` is not a
  :class:`~dt_model.model.index.GenericIndex` and must not appear inside
  an :class:`~dt_model.model.model.IOProxy`.
* :class:`MolvenoModel` subclasses :class:`~dt_model.model.model.Model`
  directly and exposes ``.cvs``, ``.pvs``, and ``.constraints`` attributes
  so that :class:`~dt_model.CrossProductEnsemble`
  and the evaluation code can consume them without modification.
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
    expose,
    graph,
    inputs,
    outputs,
)

from .molveno_presence_stats import (
    excursionist_presences_stats,
    season,
    tourist_presences_stats,
    weather,
    weekday,
)


# ---------------------------------------------------------------------------
# Constraint
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Constraint:
    """Named pairing of a usage formula index and a capacity index.

    Both *usage* and *capacity* are formula-mode or distribution-backed
    :class:`~dt_model.model.index.Index` objects, so the entire constraint is
    expressed in terms of :class:`~dt_model.model.index.GenericIndex` — no
    engine-layer types appear in the public API.

    Identity-based hashing (``eq=False``) keeps ``Constraint`` objects usable
    as dict keys, matching the convention used by ``graph.Node`` and
    ``GenericIndex``.
    """

    name: str
    usage: Index  # formula-mode Index wrapping the usage expression
    capacity: Index  # constant, distribution-backed, or formula-mode Index


# ---------------------------------------------------------------------------
# ParkingModel
# ---------------------------------------------------------------------------


@define("Parking")
class ParkingModel(Model):
    """Concern sub-model — parking usage.

    All parameters (usage factors, conversion factors, capacity) are
    received as ``Inputs`` so that callers can override any default.
    :class:`MolvenoModel` creates the indexes with their default values and
    passes them in.

    The usage formula ``i_u_parking`` is the single contractual ``Output``.
    The :class:`~overtourism.model.molveno.molveno_model.Constraint` is
    stored as a plain instance attribute ``self.constraint``.

    Attributes
    ----------
    constraint : Constraint
        The parking constraint (usage / capacity pair).
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`ParkingModel`."""

        pv_tourists: ConditionalDistributionIndex
        pv_excursionists: ConditionalDistributionIndex
        cv_weather: CategoricalIndex
        i_u_tourists_parking: Index
        i_u_excursionists_parking: Index
        i_xa_tourists_per_vehicle: Index
        i_xa_excursionists_per_vehicle: Index
        i_xo_tourists_parking: Index
        i_xo_excursionists_parking: Index
        i_c_parking: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`ParkingModel`."""

        i_u_parking: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute parking usage from inputs."""
        i_u_parking = Index(
            "parking usage",
            inputs.pv_tourists
            * inputs.i_u_tourists_parking
            / (inputs.i_xa_tourists_per_vehicle * inputs.i_xo_tourists_parking)
            + inputs.pv_excursionists
            * inputs.i_u_excursionists_parking
            / (inputs.i_xa_excursionists_per_vehicle * inputs.i_xo_excursionists_parking),
        )
        # Constraint stored as a plain attribute — not a GenericIndex.
        self.constraint = Constraint(name="parking", usage=i_u_parking, capacity=inputs.i_c_parking)
        return ParkingModel.Outputs(i_u_parking=i_u_parking)


# ---------------------------------------------------------------------------
# BeachModel
# ---------------------------------------------------------------------------


@define("Beach")
class BeachModel(Model):
    """Concern sub-model — beach usage.

    All parameters (usage factors, rotation factors, capacity) are received
    as ``Inputs``.  The uncertain rotation factor ``i_xo_tourists_beach`` is
    passed in from :class:`MolvenoModel` so it appears in the root
    ``model.indexes`` and is sampled by
    :class:`~dt_model.CrossProductEnsemble`.

    Attributes
    ----------
    constraint : Constraint
        The beach constraint (usage / capacity pair).
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`BeachModel`."""

        pv_tourists: ConditionalDistributionIndex
        pv_excursionists: ConditionalDistributionIndex
        cv_weather: CategoricalIndex
        i_u_tourists_beach: Index
        i_u_excursionists_beach: Index
        i_xo_tourists_beach: DistributionIndex
        i_xo_excursionists_beach: Index
        i_c_beach: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`BeachModel`."""

        i_u_beach: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute beach usage from inputs."""
        i_u_beach = Index(
            "beach usage",
            inputs.pv_tourists * inputs.i_u_tourists_beach / inputs.i_xo_tourists_beach
            + inputs.pv_excursionists * inputs.i_u_excursionists_beach / inputs.i_xo_excursionists_beach,
        )
        # Constraint stored as a plain attribute — not a GenericIndex.
        self.constraint = Constraint(name="beach", usage=i_u_beach, capacity=inputs.i_c_beach)
        return BeachModel.Outputs(i_u_beach=i_u_beach)


# ---------------------------------------------------------------------------
# AccommodationModel
# ---------------------------------------------------------------------------


@define("Accommodation")
class AccommodationModel(Model):
    """Concern sub-model — accommodation usage.

    Attributes
    ----------
    constraint : Constraint
        The accommodation constraint (usage / capacity pair).
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`AccommodationModel`."""

        pv_tourists: ConditionalDistributionIndex
        i_u_tourists_accommodation: Index
        i_xa_tourists_accommodation: Index
        i_c_accommodation: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`AccommodationModel`."""

        i_u_accommodation: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute accommodation usage from inputs."""
        i_u_accommodation = Index(
            "accommodation usage",
            inputs.pv_tourists * inputs.i_u_tourists_accommodation / inputs.i_xa_tourists_accommodation,
        )
        # Constraint stored as a plain attribute — not a GenericIndex.
        self.constraint = Constraint(name="accommodation", usage=i_u_accommodation, capacity=inputs.i_c_accommodation)
        return AccommodationModel.Outputs(i_u_accommodation=i_u_accommodation)


# ---------------------------------------------------------------------------
# FoodModel
# ---------------------------------------------------------------------------


@define("Food")
class FoodModel(Model):
    """Concern sub-model — food-service usage.

    Attributes
    ----------
    constraint : Constraint
        The food-service constraint (usage / capacity pair).
    """

    @inputs
    class Inputs:
        """Contractual inputs of :class:`FoodModel`."""

        pv_tourists: ConditionalDistributionIndex
        pv_excursionists: ConditionalDistributionIndex
        cv_weather: CategoricalIndex
        i_u_tourists_food: Index
        i_u_excursionists_food: Index
        i_xa_visitors_food: Index
        i_xo_visitors_food: Index
        i_c_food: DistributionIndex

    @outputs
    class Outputs:
        """Contractual outputs of :class:`FoodModel`."""

        i_u_food: Index

    def compute(self, inputs: Inputs) -> Outputs:
        """Compute food-service usage from inputs."""
        i_u_food = Index(
            "food usage",
            (inputs.pv_tourists * inputs.i_u_tourists_food + inputs.pv_excursionists * inputs.i_u_excursionists_food)
            / (inputs.i_xa_visitors_food * inputs.i_xo_visitors_food),
        )
        # Constraint stored as a plain attribute — not a GenericIndex.
        self.constraint = Constraint(name="food", usage=i_u_food, capacity=inputs.i_c_food)
        return FoodModel.Outputs(i_u_food=i_u_food)


# ---------------------------------------------------------------------------
# MolvenoModel  (root)
# ---------------------------------------------------------------------------


@define("base model")
class MolvenoModel(Model):
    """Root overtourism model that wires the four concern sub-models.

    All domain parameters are declared as ``Inputs``; supply defaults via
    :meth:`default_inputs` or override individual fields with
    :func:`dataclasses.replace`::

        m = MolvenoModel(inputs=MolvenoModel.default_inputs())
    """

    @inputs
    class Inputs:
        """All domain parameters of :class:`MolvenoModel`."""

        # Context variables
        cv_weekday: CategoricalIndex
        cv_season: CategoricalIndex
        cv_weather: CategoricalIndex
        # Presence distributions
        pv_tourists: ConditionalDistributionIndex
        pv_excursionists: ConditionalDistributionIndex
        # Distribution-backed uncertainty parameters
        i_c_parking: DistributionIndex
        i_c_beach: DistributionIndex
        i_c_accommodation: DistributionIndex
        i_c_food: DistributionIndex
        i_xo_tourists_beach: DistributionIndex
        # Parking parameters
        i_u_tourists_parking: Index
        i_u_excursionists_parking: Index
        i_xa_tourists_per_vehicle: Index
        i_xa_excursionists_per_vehicle: Index
        i_xo_tourists_parking: Index
        i_xo_excursionists_parking: Index
        # Beach parameters
        i_u_tourists_beach: Index
        i_u_excursionists_beach: Index
        i_xo_excursionists_beach: Index
        # Accommodation parameters
        i_u_tourists_accommodation: Index
        i_xa_tourists_accommodation: Index
        # Food parameters
        i_u_tourists_food: Index
        i_u_excursionists_food: Index
        i_xa_visitors_food: Index
        i_xo_visitors_food: Index
        # Presence-transformation parameters
        i_p_tourists_reduction_factor: Index
        i_p_excursionists_reduction_factor: Index
        i_p_tourists_saturation_level: Index
        i_p_excursionists_saturation_level: Index

    @outputs
    class Outputs:
        """Contractual outputs of :class:`MolvenoModel`."""

        usage_indexes: list[GenericIndex]

    @expose
    class Expose:
        """Sub-model output proxies for inspection."""

        parking: ParkingModel.Outputs
        beach: BeachModel.Outputs
        accommodation: AccommodationModel.Outputs
        food: FoodModel.Outputs

    @classmethod
    def default_inputs(cls) -> Inputs:
        """Return the default domain inputs for all parameters.

        Pass to :class:`MolvenoModel` or override individual fields with
        :func:`dataclasses.replace`::

            m = MolvenoModel(inputs=MolvenoModel.default_inputs())
        """
        cv_weekday = CategoricalIndex("weekday", {d: 1.0 / len(weekday) for d in weekday})
        cv_season = CategoricalIndex("season", {v: season[v] for v in season})
        cv_weather = CategoricalIndex("weather", {v: weather[v] for v in weather})
        pv_tourists = ConditionalDistributionIndex(
            "tourists",
            [cv_weekday, cv_season, cv_weather],
            tourist_presences_stats,
        )
        pv_excursionists = ConditionalDistributionIndex(
            "excursionists",
            [cv_weekday, cv_season, cv_weather],
            excursionist_presences_stats,
        )
        return cls.Inputs(
            cv_weekday=cv_weekday,
            cv_season=cv_season,
            cv_weather=cv_weather,
            pv_tourists=pv_tourists,
            pv_excursionists=pv_excursionists,
            # Distribution-backed uncertainty parameters
            i_c_parking=DistributionIndex("parking capacity", stats.uniform, {"loc": 350.0, "scale": 100.0}),
            i_c_beach=DistributionIndex("beach capacity", stats.uniform, {"loc": 6000.0, "scale": 1000.0}),
            i_c_accommodation=DistributionIndex(
                "accommodation capacity",
                stats.lognorm,
                {"s": 0.125, "loc": 0.0, "scale": 5000.0},
            ),
            i_c_food=DistributionIndex(
                "food service capacity",
                stats.triang,
                {"loc": 3000.0, "scale": 1000.0, "c": 0.5},
            ),
            i_xo_tourists_beach=DistributionIndex(
                "tourists on beach rotation factor",
                stats.uniform,
                {"loc": 1.0, "scale": 2.0},
            ),
            # Parking parameters
            i_u_tourists_parking=Index("tourist parking usage factor", 0.02),
            i_u_excursionists_parking=Index(
                "excursionist parking usage factor",
                graph.piecewise((0.55, cv_weather == "bad"), (0.80, True)),
            ),
            i_xa_tourists_per_vehicle=Index("tourists per vehicle allocation factor", 2.5),
            i_xa_excursionists_per_vehicle=Index("excursionists per vehicle allocation factor", 2.5),
            i_xo_tourists_parking=Index("tourists in parking rotation factor", 1.02),
            i_xo_excursionists_parking=Index("excursionists in parking rotation factor", 3.5),
            # Beach parameters
            i_u_tourists_beach=Index(
                "tourist beach usage factor",
                graph.piecewise((0.25, cv_weather == "bad"), (0.50, True)),
            ),
            i_u_excursionists_beach=Index(
                "excursionist beach usage factor",
                graph.piecewise((0.35, cv_weather == "bad"), (0.80, True)),
            ),
            i_xo_excursionists_beach=Index("excursionists on beach rotation factor", 1.02),
            # Accommodation parameters
            i_u_tourists_accommodation=Index("tourist accommodation usage factor", 0.90),
            i_xa_tourists_accommodation=Index("tourists per accommodation allocation factor", 1.05),
            # Food parameters
            i_u_tourists_food=Index("tourist food service usage factor", 0.20),
            i_u_excursionists_food=Index(
                "excursionist food service usage factor",
                graph.piecewise((0.80, cv_weather == "bad"), (0.40, True)),
            ),
            i_xa_visitors_food=Index("visitors in food service allocation factor", 0.9),
            i_xo_visitors_food=Index("visitors in food service rotation factor", 2.0),
            # Presence-transformation parameters
            i_p_tourists_reduction_factor=Index("tourists reduction factor", 1.0),
            i_p_excursionists_reduction_factor=Index("excursionists reduction factor", 1.0),
            i_p_tourists_saturation_level=Index("tourists saturation level", 10000),
            i_p_excursionists_saturation_level=Index("excursionists saturation level", 10000),
        )

    def compute(self, inputs: Inputs) -> tuple[Outputs, Expose]:
        """Wire concern sub-models from inputs."""
        parking = ParkingModel(
            inputs=ParkingModel.Inputs(
                pv_tourists=inputs.pv_tourists,
                pv_excursionists=inputs.pv_excursionists,
                cv_weather=inputs.cv_weather,
                i_u_tourists_parking=inputs.i_u_tourists_parking,
                i_u_excursionists_parking=inputs.i_u_excursionists_parking,
                i_xa_tourists_per_vehicle=inputs.i_xa_tourists_per_vehicle,
                i_xa_excursionists_per_vehicle=inputs.i_xa_excursionists_per_vehicle,
                i_xo_tourists_parking=inputs.i_xo_tourists_parking,
                i_xo_excursionists_parking=inputs.i_xo_excursionists_parking,
                i_c_parking=inputs.i_c_parking,
            )
        )
        beach = BeachModel(
            inputs=BeachModel.Inputs(
                pv_tourists=inputs.pv_tourists,
                pv_excursionists=inputs.pv_excursionists,
                cv_weather=inputs.cv_weather,
                i_u_tourists_beach=inputs.i_u_tourists_beach,
                i_u_excursionists_beach=inputs.i_u_excursionists_beach,
                i_xo_tourists_beach=inputs.i_xo_tourists_beach,
                i_xo_excursionists_beach=inputs.i_xo_excursionists_beach,
                i_c_beach=inputs.i_c_beach,
            )
        )
        accommodation = AccommodationModel(
            inputs=AccommodationModel.Inputs(
                pv_tourists=inputs.pv_tourists,
                i_u_tourists_accommodation=inputs.i_u_tourists_accommodation,
                i_xa_tourists_accommodation=inputs.i_xa_tourists_accommodation,
                i_c_accommodation=inputs.i_c_accommodation,
            )
        )
        food = FoodModel(
            inputs=FoodModel.Inputs(
                pv_tourists=inputs.pv_tourists,
                pv_excursionists=inputs.pv_excursionists,
                cv_weather=inputs.cv_weather,
                i_u_tourists_food=inputs.i_u_tourists_food,
                i_u_excursionists_food=inputs.i_u_excursionists_food,
                i_xa_visitors_food=inputs.i_xa_visitors_food,
                i_xo_visitors_food=inputs.i_xo_visitors_food,
                i_c_food=inputs.i_c_food,
            )
        )

        self.constraints = [
            parking.constraint,
            beach.constraint,
            accommodation.constraint,
            food.constraint,
        ]

        return (
            MolvenoModel.Outputs(usage_indexes=[c.usage for c in self.constraints]),
            MolvenoModel.Expose(
                parking=parking.outputs,
                beach=beach.outputs,
                accommodation=accommodation.outputs,
                food=food.outputs,
            ),
        )
