# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def save_json(data: dict, filename: Path | str) -> None:
    """Save a dictionary to a JSON file atomically."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            json.dump(data, temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    os.replace(temp_path, path)


def load_json(filename: Path | str) -> dict:
    """Load a JSON document from disk."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def get_glob(path: str | Path) -> list[str]:
    """Return all entries in a directory."""
    return [str(p) for p in Path(path).glob("*")]
