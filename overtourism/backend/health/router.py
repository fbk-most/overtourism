# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Response


def create_health_router(readiness_check: Callable[[], bool]) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["Health"])

    @router.get("/live")
    def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @router.get("/ready")
    def readiness(response: Response) -> dict[str, str]:
        if not readiness_check():
            response.status_code = 503
            return {"status": "not_ready"}
        return {"status": "ready"}

    return router
