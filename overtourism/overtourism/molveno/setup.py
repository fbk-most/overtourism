# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from overtourism.backend.api.v2.session_ownership import SessionOwnershipStore
from overtourism.backend.handler import Handler
from overtourism.dt_manager.manager.config import BaseConfig
from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig
from overtourism.dt_manager.utils.metadata import ExtrasConfig
from overtourism.overtourism.backend_extension.data import (
    MOLVENO_SIM_INDEXES,
    OvertourismIndexesLoader,
)
from overtourism.overtourism.backend_extension.viewer.viewer import ModelViewer
from overtourism.overtourism.molveno.molveno_model import (
    CV_season,
    CV_weather,
    CV_weekday,
    M_Base,
)
from overtourism.overtourism.molveno.molveno_runner import (
    Grid,
    MolvenoEvaluator,
    Sampler,
    Situation,
)

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

sampler = Sampler(target_presence_samples=target_presence_samples)

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
model_evaluator = MolvenoEvaluator(
    M_Base,
    situations=situations,
    grid=grid,
    sampler=sampler,
    index_name_map=INDEX_NAME_MAP,
    percentage_widget_ids={
        entry.index_id
        for entry in MOLVENO_SIM_INDEXES.entries
        if entry.index_category == "%"
    },
)
extras_config = ExtrasConfig(
    problem_keys=frozenset(("objective", "links", "groups", "editable_indexes")),
    proposal_keys=frozenset(("resources", "context", "impact")),
    scenario_keys=frozenset(("index_diffs")),
)


base_problem_config = BaseConfig(
    tenant="molveno",
    problem_extras=dict(
        editable_indexes=list(INDEX_NAME_MAP.keys()),
        groups=["Parcheggi", "Spiaggia", "Ristoranti", "Alberghi", "Flussi"],
    ),
)


# ──────────────────────────────────────────────
# Store
# ──────────────────────────────────────────────
data_dir = Path(__file__).parent.parent / "database"
index_data_path = data_dir / "index_data"
store_conf = StoreConfig(
    "sql",
    {"url": f"sqlite:///{data_dir / 'overtourism.sqlite'}"},
)

# ──────────────────────────────────────────────
# Manager
# ──────────────────────────────────────────────
manager_molveno = Manager(
    model=M_Base,
    model_evaluator=model_evaluator,
    store_config=store_conf,
    extras_config=extras_config,
    base_problem_config=base_problem_config,
)

MOLVENO_TENANT = base_problem_config.tenant


viewer = ModelViewer(MOLVENO_SIM_INDEXES)
data_loader = OvertourismIndexesLoader(index_data_path)


def build_handler() -> Handler:
    """Build the molveno backend handler and its collaborators."""
    data_dir = Path(__file__).parent.parent / "database"
    session_ownership_store = SessionOwnershipStore(
        data_dir / "session_ownership.sqlite"
    )

    return Handler(
        manager=manager_molveno,
        get_widgets_fn=viewer.get_widgets,
        get_widget_ids_by_groups_fn=viewer.get_widget_ids_by_groups,
        prepare_problem_extras_fn=lambda extras, payload, current_extras=None: (
            __import__(
                "overtourism.overtourism.backend_extension.api.v2.problem_extras",
                fromlist=["prepare_problem_extras"],
            ).prepare_problem_extras(
                extras,
                payload,
                current_extras,
                viewer=viewer,
            )
        ),
        arrange_data_fn=lambda data, params=None, as_snapshot=True: __import__(
            "overtourism.overtourism.molveno.molveno_runner",
            fromlist=["arrange_data"],
        ).arrange_data(
            data,
            api_version="v2",
            as_snapshot=as_snapshot,
            fields=params,
        ),
        viewer=viewer,
        prepare_values_fn=viewer.prepare_values,
        data_loader=data_loader,
        session_ownership_store=session_ownership_store,
    )
