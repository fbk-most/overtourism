# SPDX-License-Identifier: Apache-2.0
"""Loads config/settings.yaml and exposes it as module constants (the file is the only place to edit)."""

import logging
from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = PACKAGE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"

TYPE_FORMATS = ("csv", "parquet")

_PATH_KEYS = (
    "mapping",
    "raw",
    "normalized",
    "processed",
    "final",
)
_PLATFORM_KEYS = ("project", "s3_bucket", "s3_prefix", "dhcore_env")
_REFERENCE_KEYS = ("mapping_comuni", "mapping_vodafone", "mapping_apt", "geojson")
_DATASET_FILE_KEYS = ("std", "processed", "update")


def load_settings(path=SETTINGS_FILE) -> dict:
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = [
        f"{section}.{key}" if section else key
        for section, keys in (
            (
                "",
                (
                    "output_dir",
                    "type_format",
                    "paths",
                    "platform",
                    "references",
                    "datasets",
                    "phenomena",
                ),
            ),
            ("paths", _PATH_KEYS),
            ("platform", _PLATFORM_KEYS),
            ("references", _REFERENCE_KEYS),
        )
        for key in keys
        if key not in (settings.get(section, {}) if section else settings)
    ]
    for dataset_name, dataset_cfg in (settings.get("datasets") or {}).items():
        if not isinstance(dataset_cfg, dict):
            raise TypeError(f"{path}: datasets.{dataset_name} must be a mapping")
        for key in _DATASET_FILE_KEYS:
            if key not in dataset_cfg:
                missing.append(f"datasets.{dataset_name}.{key}")
    for phenomenon_name, deps in (settings.get("phenomena") or {}).items():
        if not isinstance(deps, list):
            raise TypeError(
                f"{path}: phenomena.{phenomenon_name} must be a list of dataset names"
            )
    if missing:
        raise KeyError(f"{path}: missing setting(s) {missing}")
    if settings["type_format"] not in TYPE_FORMATS:
        raise ValueError(f"{path}: type_format must be one of {TYPE_FORMATS}")
    return settings


def _resolve(base: Path, value) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else base / p


_S = load_settings()

OUTPUT_DIR = _resolve(PACKAGE_DIR, _S["output_dir"])
_P = {k: _resolve(OUTPUT_DIR, _S["paths"][k]) for k in _PATH_KEYS}

# reference mappings, shared by base build and update
MAPPING_DIR = _P["mapping"]
# base build
RAW_DIR = _P["raw"]
NORMALIZED_DIR = _P["normalized"]
PROCESSED_DIR = _P["processed"]
FINAL_DIR = _P["final"]
REFERENCES = _S["references"]

TYPE_FORMAT = _S["type_format"]
DATASET_FILES = _S["datasets"]
PHENOMENA_FILES = _S["phenomena"]

# platform (DigitalHub) / data lake
PROJECT = _S["platform"]["project"]
S3_BUCKET = _S["platform"]["s3_bucket"]
S3_PREFIX = _S["platform"]["s3_prefix"]
S3_ENV = _S["platform"]["dhcore_env"]

_LOCAL = (_S.get("update") or {}).get("local_source_dir")
LOCAL_SOURCE_DIR = _resolve(PACKAGE_DIR, _LOCAL) if _LOCAL else None


MAPPING_FILES = {
    "mapping_comuni": "mapping_comuni_ISTAT.json",
    "mapping_vodafone": "mapping_comuni_into_vodafone_Trento.json",
    "mapping_apt": "map_comuni_into_apt.json",
}


def setup_logging(level=logging.INFO):
    """Call from entry points only (libraries must not configure logging)."""
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
