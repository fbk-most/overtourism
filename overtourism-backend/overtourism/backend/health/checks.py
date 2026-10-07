# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import requests
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from overtourism.backend.utils.executor_utils import call_health_ready


def model_backend_is_ready() -> bool:
    try:
        response = call_health_ready()
    except requests.RequestException:
        return False
    return response.status_code == 200


def store_is_ready(store: object) -> bool:
    engine = getattr(store, "engine", None)
    if engine is None:
        return True

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
