# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from overtourism.backend.api.utils.config import BASE_ROUTE
from overtourism.backend.api.utils.executor_utils import list_models
from overtourism.backend.auth.dependencies import get_auth_context
from overtourism.backend.auth.enums import AuthClaim
from overtourism.backend.auth.models import AuthContext

tenant_router = APIRouter(
    prefix=f"{BASE_ROUTE}/default",
    tags=["Tenants"],
)


@tenant_router.get("/tenants", response_model=list[str])
async def list_tenants(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[str]:
    models: list[dict[str, Any]] = list_models()
    model_keys = [str(model["key"]) for model in models]

    if not context.authenticated:
        return model_keys

    claim = context.claims.get(AuthClaim.TENANT)
    if isinstance(claim, (list, tuple, set, frozenset)):
        accessible_tenants = {str(tenant) for tenant in claim}
    elif claim is None:
        accessible_tenants = set()
    else:
        accessible_tenants = {str(claim)}

    return [key for key in model_keys if key in accessible_tenants]
