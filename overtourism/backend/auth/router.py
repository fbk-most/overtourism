# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import APIRouter, Depends

from overtourism.backend.api.v1.config import BASE_ROUTE
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext

auth_router = APIRouter(prefix=f"{BASE_ROUTE}/auth")


@auth_router.get("/me", response_model=AuthContext)
async def read_auth_me(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    return context
