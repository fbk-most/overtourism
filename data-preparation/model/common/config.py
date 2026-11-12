# SPDX-License-Identifier: Apache-2.0
"""Loads model/config/settings.yaml (directories, platform) and exposes it as module constants.

Shared by the model pipelines (model/molveno, model/fazzon). The data-preparation of the territorial indexes has
its own copy (territorial_indexes/utils/config.py) with its own settings: the two point to the same Output folder.
"""

import logging
from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parents[1]  # the `model` folder
CONFIG_DIR = PACKAGE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"

TYPE_FORMATS = ("csv", "parquet")

_PATH_KEYS = ("raw", "normalized", "final")
_PLATFORM_KEYS = ("project", "s3_bucket", "s3_prefix", "dhcore_env")


def load_settings(path=SETTINGS_FILE) -> dict:
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = [
        f"{section}.{key}" if section else key
        for section, keys in (
            ("", ("output_dir", "paths", "platform")),
            ("paths", _PATH_KEYS),
            ("platform", _PLATFORM_KEYS),
        )
        for key in keys
        if key not in (settings.get(section, {}) if section else settings)
    ]
    if missing:
        raise KeyError(f"{path}: missing setting(s) {missing}")
    return settings


def _resolve(base: Path, value) -> Path:
    p = Path(value).expanduser()
    return (p if p.is_absolute() else base / p).resolve()


_S = load_settings()

OUTPUT_DIR = _resolve(PACKAGE_DIR, _S["output_dir"])
_P = {k: _resolve(OUTPUT_DIR, _S["paths"][k]) for k in _PATH_KEYS}
RAW_DIR = _P["raw"]
NORMALIZED_DIR = _P["normalized"]
FINAL_DIR = _P["final"]

# platform (DigitalHub) / data lake
PROJECT = _S["platform"]["project"]
S3_BUCKET = _S["platform"]["s3_bucket"]
S3_PREFIX = _S["platform"]["s3_prefix"]
S3_ENV = _S["platform"]["dhcore_env"]


def setup_logging(level=logging.INFO):
    """Call from entry points only (libraries must not configure logging)."""
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
