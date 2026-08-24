# SPDX-License-Identifier: Apache-2.0
"""Model-key -> Backend wiring for the REST API.

`FazzonBackend` and `MolvenoBackend` share an identical public contract
(`parameter_schema()`, `evaluate()`) by convention even though there is no
shared base class (see `overtourism/BACKEND_DESIGN.md` §Layer 3) — this
registry is what lets `overtourism.layer_3.api.routes` expose one generic
route set parameterized by `model_key` instead of duplicating routes per
model.
"""

from __future__ import annotations

import functools

from overtourism.layer_3.model.fazzon.fazzon_backend import FazzonBackend
from overtourism.layer_3.model.molveno.molveno_backend import MolvenoBackend

BACKEND_REGISTRY: dict[str, type[FazzonBackend | MolvenoBackend]] = {
    "fazzon": FazzonBackend,
    "molveno": MolvenoBackend,
}

MODEL_TITLES: dict[str, str] = {
    "fazzon": "Fazzon (Lago dei Caprioli)",
    "molveno": "Molveno",
}


@functools.cache
def get_backend(model_key: str) -> FazzonBackend | MolvenoBackend:
    """Return the (process-wide, lazily-built) backend instance for `model_key`.

    Mirrors the `st.cache_resource`-memoized backend construction the
    Streamlit dashboards already use — each backend is expensive enough to
    build once per process, not per-request.

    Raises
    ------
    KeyError
        If `model_key` is not in `BACKEND_REGISTRY`.
    """
    backend_cls = BACKEND_REGISTRY[model_key]
    return backend_cls()
