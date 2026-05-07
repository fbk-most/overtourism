# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime


def get_timestamp() -> str:
    """Return the current timezone-aware timestamp.

    Returns
    -------
    str
        Current timestamp in ISO 8601 format.
    """
    return datetime.now().astimezone().isoformat()
