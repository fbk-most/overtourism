# SPDX-License-Identifier: Apache-2.0
import os
import typing

import requests

model_backend_url = os.environ.get("MODEL_BACKEND_URL", "http://localhost:8001")


def call_executor(
    tenant: str,
    param_overrides: dict[str, typing.Any] | None = None,
    as_snapshot: bool = False,
) -> dict[str, typing.Any]:
    """Call the backend executor with the provided parameters."""
    if param_overrides is None:
        param_overrides = {}
    params = {"as_snapshot": str(as_snapshot).lower()}
    base_url = f"{model_backend_url}/models/{tenant}/evaluate"
    return requests.post(
        base_url, json={"param_overrides": param_overrides}, params=params
    ).json()


def list_models() -> list[dict[str, typing.Any]]:
    """Call the backend model list endpoint."""
    base_url = f"{model_backend_url}/models"
    return requests.get(base_url).json()


def call_schema(
    tenant: str,
) -> dict[str, typing.Any]:
    """Call the backend schema endpoint for the provided tenant."""
    base_url = f"{model_backend_url}/models/{tenant}/schema"
    r = requests.get(base_url)
    r.raise_for_status()
    return r.json()
