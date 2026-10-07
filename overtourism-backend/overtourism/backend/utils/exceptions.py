# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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
