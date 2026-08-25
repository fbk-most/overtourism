# SPDX-License-Identifier: Apache-2.0
"""REST routes over the Layer 3 computation backends.

One generic route set parameterized by `{model_key}` rather than one router
per model (contrast `overtourism.OLD/backend/api/`, whose routers diverge
per-concern because that Layer 4 was keyed by `problem_id`) — Fazzon and
Molveno backends already share an identical contract (§Layer 3), so a single
router covers both.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from overtourism.layer_3.api.registry import (
    BACKEND_REGISTRY,
    MODEL_TITLES,
    get_backend,
)
from overtourism.layer_3.api.schemas import (
    EvaluateRequest,
    EvaluateResponse,
    ModelInfo,
)
from overtourism.layer_3.model.common.sustainability_field import (
    OvertourismParameterMeta,
)

router = APIRouter(prefix="/models", tags=["models"])


def _get_backend_or_404(model_key: str):
    try:
        return get_backend(model_key)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Unknown model: {model_key!r}"
        ) from None


@router.get("", response_model=list[ModelInfo])
def list_models() -> list[ModelInfo]:
    """List the available models."""
    return [ModelInfo(key=key, title=MODEL_TITLES[key]) for key in BACKEND_REGISTRY]


@router.get("/{model_key}/schema", response_model=list[OvertourismParameterMeta])
def get_schema(model_key: str) -> list[OvertourismParameterMeta]:
    """Return the model's ordered, self-describing parameter schema."""
    backend = _get_backend_or_404(model_key)
    return backend.parameter_schema()


@router.post("/{model_key}/evaluate", response_model=EvaluateResponse)
def evaluate(model_key: str, body: EvaluateRequest) -> EvaluateResponse:
    """Evaluate the model under the given string-keyed parameter overrides."""
    backend = _get_backend_or_404(model_key)
    output = backend.evaluate(body.param_overrides)
    return EvaluateResponse.from_output(output)
