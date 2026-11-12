# SPDX-License-Identifier: Apache-2.0
"""Configuration of the Molveno pipeline: molveno.yaml (sources) + settings.yaml (directories, platform)."""

from pathlib import Path

from model.common.sources import SourcesConfig, load_sources_config
from model.common.config import FINAL_DIR, NORMALIZED_DIR, RAW_DIR

MOLVENO_DIR = Path(__file__).resolve().parent
CONFIG_FILE = MOLVENO_DIR / "molveno.yaml"

MOLVENO_RAW_DIR = RAW_DIR / "molveno"
MOLVENO_NORMALIZED_DIR = NORMALIZED_DIR / "molveno"
MOLVENO_FINAL_DIR = FINAL_DIR / "molveno"


def load_config(path=CONFIG_FILE, local_source_dir=None) -> SourcesConfig:
    return load_sources_config(path, local_source_dir)
