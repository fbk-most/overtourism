# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

EDITABLE_INDEXES_KEY = "editable_indexes"


def get_problem_editable_indexes(extras: dict) -> list[str]:
    value = extras.get(EDITABLE_INDEXES_KEY, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def set_problem_editable_indexes(
    extras: dict,
    editable_indexes: list[str] | None,
) -> None:
    if editable_indexes is None:
        extras.pop(EDITABLE_INDEXES_KEY, None)
        return

    extras[EDITABLE_INDEXES_KEY] = list(editable_indexes)


def with_problem_editable_indexes(
    extras: dict | None,
    editable_indexes: list[str] | None,
) -> dict:
    resolved_extras = {} if extras is None else extras
    set_problem_editable_indexes_like_dict(resolved_extras, editable_indexes)
    return resolved_extras


def set_problem_editable_indexes_like_dict(
    extras: dict,
    editable_indexes: list[str] | None,
) -> None:
    if editable_indexes is None:
        extras.pop(EDITABLE_INDEXES_KEY, None)
        return

    extras[EDITABLE_INDEXES_KEY] = list(editable_indexes)
