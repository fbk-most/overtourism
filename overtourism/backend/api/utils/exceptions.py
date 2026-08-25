# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BackendException(HTTPException):
    """Base exception for backend errors."""


class ProblemNotFound(BackendException):
    def __init__(self, detail: str = "Problem not found") -> None:
        super().__init__(status_code=404, detail=detail)


class InternalServerError(BackendException):
    def __init__(self, detail: str = "Internal server error") -> None:
        super().__init__(status_code=500, detail=detail)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation failed",
                "errors": [
                    _serialize_validation_error(error) for error in exc.errors()
                ],
            },
        )


def _serialize_validation_error(error: dict[str, Any]) -> dict[str, str]:
    location = error.get("loc", ())
    field = ".".join(str(part) for part in location) or "request"
    return {
        "field": field,
        "message": str(error.get("msg", "Invalid request")),
        "type": str(error.get("type", "validation_error")),
    }
