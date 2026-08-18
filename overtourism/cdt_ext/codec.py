# SPDX-License-Identifier: Apache-2.0
"""Decoder for `ModelOutput.to_snapshot()`'s array-field encoding.

Kept separate from `runner_ext.py` deliberately: this module has no
dependency on `scipy`/`civic_digital_twins` (only `base64` + `numpy`), so
code that only needs `decode_array` — e.g. an HTTP-based Layer 5 client that
will eventually run in a different container from Layers 1-3 (see
`overtourism/BACKEND_DESIGN.md`) — doesn't have to import that whole
dependency chain just to decode a JSON field.
"""

from __future__ import annotations

import base64
from typing import Any

import numpy as np

__all__ = ["decode_array"]


def decode_array(d: dict[str, Any]) -> np.ndarray:
    """Decode a numpy array from `ModelOutput._serialize()`'s per-field encoding.

    `ModelOutput.to_snapshot()`/`_serialize()` (the `civic_digital_twins`
    library's own dataclass summary serializer) encodes each `np.ndarray`
    field as ``{"data": ..., "dtype": ..., "shape": ..., "encoding": "json"?}``
    — base64 for numeric dtypes, a plain JSON list for object dtypes (e.g.
    categorical string assignments). This is the inverse, mirroring the
    library's own (module-private) ``_decode_array``.

    The natural fix is for the library to expose this itself
    (`_serialize()`/`to_snapshot()` could take an output-type parameter
    selecting a portable plain-JSON encoding instead of base64), at which
    point this function is deleted in favour of the library's own, same as
    every other `cdt_ext` staging item.

    Note
    ----
    The base64 numeric path assumes the same byte order as the encoding
    host (no explicit endianness is stored) — sound for same-architecture
    client/server pairs, not a portable wire format across differing
    endianness.
    """
    if d.get("encoding") == "json":
        return np.array(d["data"], dtype=object).reshape(tuple(d["shape"]))
    raw = base64.b64decode(d["data"].encode("ascii"))
    return (
        np.frombuffer(raw, dtype=np.dtype(d["dtype"])).reshape(tuple(d["shape"])).copy()
    )
