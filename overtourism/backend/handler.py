# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from overtourism.backend.data.loader import OvertourismIndexesLoader
    from overtourism.backend.data.viewer.viewer import ModelViewer
    from overtourism.dt_manager.manager.manager import Manager
    from overtourism.overtourism.adapters.utils import ArrangeDataFn


class Handler:
    """
    Container for backend singletons.
    """

    def __init__(
        self,
        manager: Manager,
        viewer: ModelViewer | None = None,
        data_loader: OvertourismIndexesLoader | None = None,
        arrange_data_fn: ArrangeDataFn | None = None,
        prepare_values_fn: typing.Callable[..., dict] | None = None,
    ) -> None:
        self.manager = manager
        self.viewer = viewer
        self.data_loader = data_loader
        self.arrange_data_fn = arrange_data_fn
        self.prepare_values_fn = prepare_values_fn
