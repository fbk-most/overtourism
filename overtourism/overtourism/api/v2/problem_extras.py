# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from overtourism.overtourism.viewer import WidgetViewerLike


def prepare_problem_extras(
    extras: dict[str, Any],
    payload: dict[str, Any],
    current_extras: dict[str, Any] | None = None,
    *,
    viewer: WidgetViewerLike | None = None,
) -> dict[str, Any]:
    """Merge overtourism problem extras and keep editable indexes in sync."""
    merged_extras = dict(current_extras or {})
    merged_extras.update(extras)
    payload_extras = payload.get("extras")
    if isinstance(payload_extras, dict):
        merged_extras.update(payload_extras)

    groups = [str(group) for group in merged_extras.get("groups", [])]
    editable_indexes = merged_extras.get("editable_indexes", [])
    if viewer is not None and groups:
        editable_indexes = viewer.get_widget_ids_by_groups(groups)
    merged_extras["editable_indexes"] = [str(item) for item in editable_indexes]
    return merged_extras
