# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Widgets(BaseModel):
    widgets: dict[str, Any]
