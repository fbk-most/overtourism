# SPDX-License-Identifier: Apache-2.0
"""Adapters for the Vodafone presences source."""

import pandas as pd

from utils.adapters.base import RawData, register_adapter


@register_adapter("vodafone_raw", kind="vodafone")
def vodafone_raw(raw: RawData) -> pd.DataFrame:
    """Vodafone export already in the expected layout (locId, date, value, ...): returned unchanged."""
    return raw.df
