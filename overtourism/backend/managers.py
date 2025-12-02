# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import digitalhub as dh

from overtourism.backend.config import (
    artifacts,
    dataitems,
    index_data_path,
    manager_name,
    metadata_path,
    module_name,
    module_path,
    project_name,
    viewer_name,
    standalone_mode
)
from overtourism.backend.data.loader import OvertourismIndexesLoader
from overtourism.backend.metadata.manager import MetadataManager
from overtourism.backend.shared.utils import load_class
from overtourism.dt_studio.manager.problem.manager import ProblemManager
from overtourism.dt_studio.viewer.viewer import ModelViewer

logger = logging.getLogger(__name__)

print("Initializing data...")

if standalone_mode:
    logger.info("Standalone mode enabled")
else:
    # Collect data
    p = dh.get_or_create_project(project_name)
    for d in dataitems:
        logger.info(f"Downloading dataitem: {d}")
        p.get_dataitem(d).download(f"{index_data_path}/{d}.parquet", overwrite=True)
    for a in artifacts:
        logger.info(f"Downloading artifact: {a}")
        p.get_artifact(a).download(index_data_path, overwrite=True)


# Load problem manager
problem_manager: ProblemManager = load_class(module_name, module_path, manager_name)
problem_manager.import_problems()
logger.info("Problem manager loaded and problems imported")

# Load viewer
viewer: ModelViewer = load_class(module_name, module_path, viewer_name)
logger.info("Model viewer loaded")

# Metadata manager
metadata_manager = MetadataManager(metadata_path)
logger.info("Metadata manager initialized")

# Overtourism indexes dataloader
overtourism_indexes_data_loader = OvertourismIndexesLoader(index_data_path)
logger.info("Overtourism indexes loader initialized")
