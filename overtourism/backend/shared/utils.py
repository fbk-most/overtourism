# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import typing
from datetime import datetime
from uuid import uuid4

if typing.TYPE_CHECKING:
    pass


BASE_ROUTE = "/api/v1"


def load_class(module_name: str, path: str, instance_name: str) -> typing.Any:
    """Load an instance from a Python module file by attribute name."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        raise ImportError(f"Module '{module_name}' not found in path {path}")
    imported_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported_module)
    return getattr(imported_module, instance_name)


def get_id(scenario_id: str, session_id: str) -> str:
    return f"{scenario_id}_{session_id}_{uuid4().hex}"


def get_timestamp() -> str:
    """Get the current timestamp timezoned."""
    return datetime.now().astimezone().isoformat()
