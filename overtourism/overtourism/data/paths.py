# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def get_index_data_path() -> Path:
    return Path(__file__).resolve().parent / "index_data"
