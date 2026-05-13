# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from overtourism.dt_manager.classes.metadata import ExtrasConfig
from overtourism.dt_manager.manager.config import BaseProblemConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.overtourism.adapters.evaluator import (
    Grid,
    OvertourismEvaluator,
    Sampler,
    Situation,
)
from overtourism.overtourism.molveno_model import (
    CV_season,
    CV_weather,
    CV_weekday,
    M_Base,
    PV_excursionists,
    PV_tourists,
)
from overtourism.overtourism.overtourism_metamodel import OvertourismEnsemble

# ──────────────────────────────────────────────
# Widget index_id → model index name mapping
# ──────────────────────────────────────────────
INDEX_NAME_MAP: dict[str, str] = {
    # Capacities
    "available_parking_spaces": "parking capacity",
    "available_beach_seats": "beach capacity",
    "available_beds": "accommodation capacity",
    "available_restaurant_seats": "food service capacity",
    # Usage factors
    "tourists_parking_percentage": "tourist parking usage factor",
    "excursionists_parking_percentage": "excursionist parking usage factor",
    "tourists_beach_percentage": "tourist beach usage factor",
    "excursionists_beach_percentage": "excursionist beach usage factor",
    "tourists_accommodation_percentage": "tourist accommodation usage factor",
    "tourists_restaurant_percentage": "tourist food service usage factor",
    # Allocation factors
    "tourists_per_vehicle_average": "tourists per vehicle allocation factor",
    "excursionists_per_vehicle_average": "excursionists per vehicle allocation factor",
    "tourists_accommodation_allocation_factor": "tourists per accommodation allocation factor",
    "visitors_food_allocation_factor": "visitors in food service allocation factor",
    # Rotation / turnover factors
    "tourists_parking_turnover": "tourists in parking rotation factor",
    "excursionists_parking_turnover": "excursionists in parking rotation factor",
    "tourists_beach_turnover": "tourists on beach rotation factor",
    "excursionists_beach_turnover": "excursionists on beach rotation factor",
    "visitors_food_turnover": "visitors in food service rotation factor",
    # Presence transform
    "tourists_reduction_factor": "tourists reduction factor",
    "excursionists_reduction_factor": "excursionists reduction factor",
    "tourists_saturation_level": "tourists saturation level",
    "excursionists_saturation_level": "excursionists saturation level",
}

# ──────────────────────────────────────────────
# Grid
# ──────────────────────────────────────────────
(t_max, e_max) = (10000, 10000)
n_samples = 100

grid = Grid(x_max=t_max, y_max=e_max, n_samples=n_samples)

# ──────────────────────────────────────────────
# Sampler
# ──────────────────────────────────────────────
target_presence_samples = 1200

sampler = Sampler(
    target_presence_samples=target_presence_samples,
    reduction_indexes={
        PV_tourists.name: "tourists reduction factor",
        PV_excursionists.name: "excursionists reduction factor",
    },
    saturation_indexes={
        PV_tourists.name: "tourists saturation level",
        PV_excursionists.name: "excursionists saturation level",
    },
)

# ──────────────────────────────────────────────
# Situations
# ──────────────────────────────────────────────
situations = [
    Situation("default", "Condizioni medie di riferimento", {}),
    Situation("good_weather", "Meteo > Bel tempo", {CV_weather: ["good", "unsettled"]}),
    Situation("bad_weather", "Meteo > Cattivo tempo", {CV_weather: ["bad"]}),
    Situation("high_season", "Stagione > Alta", {CV_season: ["high", "very high"]}),
    Situation("low_season", "Stagione > Bassa", {CV_season: ["low", "mid"]}),
    Situation(
        "weekend_days",
        "Giorni settimana > Fine settimana",
        {CV_weekday: ["saturday", "sunday"]},
    ),
    Situation(
        "working_days",
        "Giorni settimana > Giorni lavorativi",
        {CV_weekday: ["monday", "tuesday", "wednesday", "thursday", "friday"]},
    ),
]

# ──────────────────────────────────────────────
# Adapters
# ──────────────────────────────────────────────
model_evaluator = OvertourismEvaluator(
    ensemble_class=OvertourismEnsemble,
    situations=situations,
    grid=grid,
    sampler=sampler,
    index_name_map=INDEX_NAME_MAP,
)
extras_config = ExtrasConfig(
    problem_keys=frozenset(("objective", "links", "groups", "editable_indexes")),
    proposal_keys=frozenset(("resources", "context", "impact")),
)


base_problem_config = BaseProblemConfig(
    problem_extras=dict(
        editable_indexes=list(INDEX_NAME_MAP.keys()),
        groups=["Parcheggi", "Spiaggia", "Ristoranti", "Alberghi", "Flussi"],
    ),
    scenario_id="model_0",
)


# ──────────────────────────────────────────────
# Store
# ──────────────────────────────────────────────
data_dir = Path(__file__).parent / "data"
store_conf = StoreConfig(
    "sql",
    {"url": f"sqlite:///{data_dir / 'overtourism.sqlite'}"},
)

# ──────────────────────────────────────────────
# Manager
# ──────────────────────────────────────────────
manager = Manager(
    model=M_Base,
    model_evaluator=model_evaluator,
    store_config=store_conf,
    extras_config=extras_config,
    base_problem_config=base_problem_config,
)
