# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime


def get_timestamp() -> str:
    """Return the current timezone-aware timestamp.

    Returns
    -------
    str
        Current timestamp in ISO 8601 format.
    """
    return datetime.now().astimezone().isoformat()


def parse_timestamp(timestamp: str) -> datetime:
    """Parse an ISO 8601 timestamp and normalize it to UTC."""
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
