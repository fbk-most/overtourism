# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path

import digitalhub as dh
from digitalhub.utils.exceptions import StoreError

# Platform specific settings
project_name = os.getenv("PROJECT_NAME", "overtourism")
dataitems = [
    "df_distribuzione_feriale",
    "df_distribuzione_festivo",
    "df_distribuzione_prefestivo",
    "df_flussi_estate",
    "df_incidenza_postiletto_non_conv",
    "df_incidenza_strutture_non_conv",
    "df_overturismo",
    "df_stagionalita_presenze",
    "df_tasso_ricettivita",
    "df_tasso_turisticita_estate",
    "df_tasso_turisticita",
    "df_tasso_variazione_pecentuale",
    "df_turismo_sommerso",
]
artifacts = [
    "map_apt.geojson",
    "map_comuni.geojson",
    "map_vodafone_2024.geojson",
    "map_vodafone.geojson",
]


def download_index_data() -> None:
    """Download the index data from the digitalhub platform."""

    project = dh.get_project(project_name)
    download_dir = Path(__file__).parent / "database" / "index_data"
    download_dir.mkdir(parents=True, exist_ok=True)

    for dataitem in dataitems:
        print(f"Downloading dataitem: {dataitem}")
        try:
            project.get_dataitem(dataitem).download(str(download_dir))
        except StoreError as e:
            print(f"Failed to download dataitem {dataitem}: {e}")

    for artifact in artifacts:
        print(f"Downloading artifact: {artifact}")
        try:
            project.get_artifact(artifact).download(str(download_dir))
        except StoreError as e:
            print(f"Failed to download artifact {artifact}: {e}")
