# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Protocol


class WidgetViewerLike(Protocol):
    def get_widgets(
        self,
        values: dict[str, Any],
        language: str = "it",
    ) -> dict[str, Any]: ...

    def get_widget_ids_by_groups(self, groups: list[str]) -> list[str]: ...
