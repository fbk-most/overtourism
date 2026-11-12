# SPDX-License-Identifier: Apache-2.0
"""Configuration of the Fazzon pipeline: fazzon.yaml (sources) + settings.yaml (directories, platform)."""

from pathlib import Path

from model.common.sources import SourcesConfig, load_sources_config
from model.common.config import FINAL_DIR, NORMALIZED_DIR, RAW_DIR

FAZZON_DIR = Path(__file__).resolve().parent
CONFIG_FILE = FAZZON_DIR / "fazzon.yaml"
STATIONS_FILE = FAZZON_DIR / "reference" / "stations.csv"

FAZZON_RAW_DIR = RAW_DIR / "fazzon"
FAZZON_NORMALIZED_DIR = NORMALIZED_DIR / "fazzon"
FAZZON_FINAL_DIR = FINAL_DIR / "fazzon"


def load_config(path=CONFIG_FILE, local_source_dir=None) -> SourcesConfig:
    return load_sources_config(path, local_source_dir)
