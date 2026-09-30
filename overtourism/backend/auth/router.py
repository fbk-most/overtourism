# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.models import AuthContext, AuthMeResponse

auth_router = APIRouter(prefix="/auth")


@auth_router.get("/me", response_model=AuthMeResponse)
async def read_auth_me(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthMeResponse:
    return AuthMeResponse(
        authenticated=context.authenticated,
        territory=context.territory,
        subject=context.subject,
    )
