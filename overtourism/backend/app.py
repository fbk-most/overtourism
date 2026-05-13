# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from overtourism.backend.api.data import data_router
from overtourism.backend.api.main import create_app
from overtourism.backend.data.catalog import MOLVENO_SIM_INDEXES
from overtourism.backend.data.loader import OvertourismIndexesLoader
from overtourism.backend.data.viewer.viewer import ModelViewer
from overtourism.backend.handler import Handler
from overtourism.overtourism.adapters.utils import arrange_data
from overtourism.overtourism.setup import manager

viewer = ModelViewer(MOLVENO_SIM_INDEXES)
data_loader = OvertourismIndexesLoader(
    str(Path(__file__).parent / "model" / "data" / "index_data")
)

handler = Handler(
    manager=manager,
    arrange_data_fn=arrange_data,
    viewer=viewer,
    prepare_values_fn=viewer.prepare_values,
    data_loader=data_loader,
)

app = create_app(
    handler,
    title="AIxPA Over-Tourism API",
    version="0.1.0",
    description="API for tourism indices in Trentino",
    extra_routers=[data_router],
)
