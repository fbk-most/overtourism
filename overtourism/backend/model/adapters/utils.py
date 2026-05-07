# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Callable

# Type alias used by Managers
ArrangeDataFn = Callable[[dict], dict]


def arrange_data(data: dict) -> dict:
    """Transform OvertourismOutputData into the API response format."""
    d = {}
    d["points"] = {}
    d["points"]["uncertainty"] = []
    d["points"]["uncertainty_by_constraint"] = {}
    for i in data["uncertainty_by_constraint"].keys():
        d["points"]["uncertainty_by_constraint"][i] = []

    for i in list(
        zip(
            data["sample_x"],
            data["sample_y"],
            data["uncertainty"],
            data["usage"],
            data["usage_uncertainty"],
        )
    ):
        d["points"]["uncertainty"].append(
            {
                "tourists": i[0],
                "excursionists": i[1],
                "index": i[2],
                "usage": i[3],
                "usage_uncertainty": i[4],
            }
        )

    for k, v in data["uncertainty_by_constraint"].items():
        for i in list(
            zip(
                data["sample_x"],
                data["sample_y"],
                v,
                data["usage_by_constraint"][k],
                data["usage_uncertainty_by_constraint"][k],
            )
        ):
            d["points"]["uncertainty_by_constraint"][k].append(
                {
                    "tourists": i[0],
                    "excursionists": i[1],
                    "index": i[2],
                    "usage": i[3],
                    "usage_uncertainty": i[4],
                }
            )

    d["kpis"] = data["kpis"]
    d["x_max"] = data["x_max"]
    d["y_max"] = data["y_max"]
    d["capacity_mean"] = data["capacity_mean"]
    d["capacity_mean_by_constraint"] = data["capacity_mean_by_constraint"]
    d["constraint_curves"] = data["constraint_curves"]
    return d
