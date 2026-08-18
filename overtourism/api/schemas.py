# SPDX-License-Identifier: Apache-2.0
"""Pydantic request models for the REST API.

`/evaluate` returns `SustainabilityFieldOutput.to_snapshot()` directly (see
`overtourism.api.routes`) rather than a hand-rolled response shape — it is
already the library's own purpose-built, tested serializer, and the only
consumer today (`overtourism.dt_studio.dashboard.http_adapter`) is code we
control, so decoding its base64-encoded array fields
(`overtourism.cdt_ext.codec.decode_array`) once on the client side costs
less than maintaining a parallel schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """One entry in the `GET /models` catalogue."""

    key: str
    title: str


class EvaluateRequest(BaseModel):
    """Body of `POST /models/{model_key}/evaluate`.

    `param_overrides` mirrors `Backend.evaluate()`'s signature: a partial
    `{index_name: value}` mapping. Scalars are `float`, distributions are
    `(lo, hi)` pairs (JSON arrays of length 2), categoricals are `str`. Keys
    absent from the mapping use model defaults.
    """

    param_overrides: dict[str, Any] = Field(default_factory=dict)
