# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from overtourism.backend.api.v2.session_ownership import SessionOwnershipStore
    from overtourism.dt_manager.manager.manager import Manager



class Handler:
    """
    Container for backend singletons.
    """

    def __init__(
        self,
        manager: Manager,
        session_ownership_store: SessionOwnershipStore | None = None,
    ) -> None:
        self.manager = manager
        self.session_ownership_store = session_ownership_store
