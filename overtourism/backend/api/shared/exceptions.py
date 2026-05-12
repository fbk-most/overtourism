# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import HTTPException


class BackendException(HTTPException):
    """Base exception for backend errors."""


class ProblemNotFound(BackendException):
    def __init__(self, detail: str = "Problem not found") -> None:
        super().__init__(status_code=404, detail=detail)


class InternalServerError(BackendException):
    def __init__(self, detail: str = "Internal server error") -> None:
        super().__init__(status_code=500, detail=detail)
