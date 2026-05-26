# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from typing import Any, Callable, Protocol

if typing.TYPE_CHECKING:
    from overtourism.dt_manager.manager.manager import Manager


class DataLoaderLike(Protocol):
    def get_categories(self, language: str = "it") -> dict[str, Any]: ...

    def get_list(
        self,
        category: str = "",
        language: str = "it",
    ) -> dict[str, Any]: ...

    def get_dataframe(self, dataframe: str) -> dict[str, Any]: ...

    def get_map(self, map_name: str) -> dict[str, Any]: ...


class GetWidgetsFnLike(Protocol):
    def __call__(
        self,
        values: dict[str, Any],
        language: str = "it",
    ) -> dict[str, Any]: ...


class GetWidgetIdsByGroupsFnLike(Protocol):
    def __call__(self, groups: list[str]) -> list[str]: ...


class ArrangeDataFnLike(Protocol):
    def __call__(
        self,
        data: Any,
        params: list[str] | None = None,
    ) -> dict[str, Any]: ...


class PrepareProblemExtrasFnLike(Protocol):
    def __call__(
        self,
        extras: dict[str, Any],
        payload: dict[str, Any],
        current_extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class Handler:
    """
    Container for backend singletons.
    """

    def __init__(
        self,
        manager: Manager,
        viewer: Any | None = None,
        data_loader: DataLoaderLike | None = None,
        get_widgets_fn: GetWidgetsFnLike | None = None,
        get_widget_ids_by_groups_fn: GetWidgetIdsByGroupsFnLike | None = None,
        prepare_problem_extras_fn: PrepareProblemExtrasFnLike | None = None,
        arrange_data_fn: ArrangeDataFnLike | None = None,
        prepare_values_fn: Callable[..., dict] | None = None,
    ) -> None:
        self.manager = manager
        self.viewer = viewer
        self.data_loader = data_loader
        self.get_widgets_fn = get_widgets_fn
        self.get_widget_ids_by_groups_fn = get_widget_ids_by_groups_fn
        self.prepare_problem_extras_fn = prepare_problem_extras_fn
        self.arrange_data_fn = arrange_data_fn
        self.prepare_values_fn = prepare_values_fn
