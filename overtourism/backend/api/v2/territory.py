# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.config import BASE_ROUTE
from overtourism.backend.api.utils.executor_utils import list_models
from overtourism.backend.auth.tokens.context import AuthContext
from overtourism.backend.auth.tokens.dependencies import get_auth_context
from overtourism.backend.auth.tokens.enums import AuthClaim

territory_router = APIRouter(
    prefix=f"{BASE_ROUTE}/default",
    tags=["Territorys"],
)


@territory_router.get("/territorys", response_model=list[str])
async def list_territorys(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[str]:
    models: list[dict[str, Any]] = list_models()
    model_keys = [str(model["key"]) for model in models]

    if not context.authenticated:
        return model_keys

    claim = context.claims.get(AuthClaim.TERRITORY)
    if isinstance(claim, (list, tuple, set, frozenset)):
        accessible_territorys = {str(territory) for territory in claim}
    elif claim is None:
        accessible_territorys = set()
    else:
        accessible_territorys = {str(claim)}

    return [key for key in model_keys if key in accessible_territorys]
