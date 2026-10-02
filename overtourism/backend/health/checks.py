# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


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
