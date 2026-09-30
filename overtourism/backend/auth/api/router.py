# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from overtourism.backend.auth.api.models import (
    AuthMeResponse,
    AuthRoleResponse,
    AuthUserResponse,
    CreateAuthUserRequest,
    UpdateAuthUserRequest,
)
from overtourism.backend.auth.identity.authorization import (
    get_current_user,
    get_user_manager,
    require_global_admin,
    resolve_current_user,
)
from overtourism.backend.auth.identity.user_manager import UserManager
from overtourism.backend.auth.identity.users import User, UserRole
from overtourism.backend.auth.tokens.context import AuthContext
from overtourism.backend.auth.tokens.dependencies import get_auth_context
from overtourism.backend.handler import Handler, get_handler

auth_router = APIRouter(prefix="/auth")

_ROLE_DESCRIPTIONS = {
    UserRole.ADMIN: "Global administrator with access to all territories.",
    UserRole.MULTIEDITOR: "Editor assigned to one or more territories.",
    UserRole.EDITOR: "Editor assigned to exactly one territory.",
    UserRole.VIEWER: "Read-only user assigned to exactly one territory.",
}


def _user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        user_id=user.user_id,
        identifier=user.identifier,
        subject=user.subject,
        role=user.role,
        is_active=user.is_active,
        territories=sorted(user.territories),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@auth_router.get("/me", response_model=AuthMeResponse)
async def read_auth_me(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    handler: Annotated[Handler, Depends(get_handler)],
) -> AuthMeResponse:
    user = resolve_current_user(context, handler)
    return AuthMeResponse(
        authenticated=context.authenticated,
        territory=context.territory,
        subject=context.subject,
        user_id=None if user is None else user.user_id,
        role=None if user is None else user.role,
        is_global_admin=user is not None and user.role is UserRole.ADMIN,
        territories=[] if user is None else sorted(user.territories),
    )


@auth_router.get(
    "/roles",
    response_model=list[AuthRoleResponse],
    dependencies=[Depends(get_current_user)],
)
async def read_auth_roles() -> list[AuthRoleResponse]:
    return [
        AuthRoleResponse(role=role, description=description)
        for role, description in _ROLE_DESCRIPTIONS.items()
    ]


@auth_router.get(
    "/users",
    response_model=list[AuthUserResponse],
    dependencies=[Depends(require_global_admin)],
)
async def list_auth_users(
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
    territory: Annotated[str | None, Query()] = None,
) -> list[AuthUserResponse]:
    return [
        _user_response(user) for user in user_manager.list_users(territory=territory)
    ]


@auth_router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthUserResponse,
    dependencies=[Depends(require_global_admin)],
)
async def create_auth_user(
    data: CreateAuthUserRequest,
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
) -> AuthUserResponse:
    try:
        user = user_manager.create_user(
            identifier=data.identifier,
            role=data.role,
            territories=data.territories,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this identifier already exists",
        ) from exc
    return _user_response(user)


@auth_router.patch(
    "/users/{user_id}",
    response_model=AuthUserResponse,
    dependencies=[Depends(require_global_admin)],
)
async def update_auth_user(
    user_id: str,
    data: UpdateAuthUserRequest,
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
) -> AuthUserResponse:
    if all(value is None for value in (data.role, data.territories, data.is_active)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one user field must be provided",
        )
    try:
        user = user_manager.update_user(
            user_id,
            role=data.role,
            territories=data.territories,
            is_active=data.is_active,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this identifier already exists",
        ) from exc
    return _user_response(user)


@auth_router.delete(
    "/users/{user_id}",
    response_model=AuthUserResponse,
    dependencies=[Depends(require_global_admin)],
)
async def deactivate_auth_user(
    user_id: str,
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
) -> AuthUserResponse:
    try:
        user = user_manager.deactivate_user(user_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    return _user_response(user)


@auth_router.post(
    "/users/reload",
    dependencies=[Depends(require_global_admin)],
)
async def reload_auth_users(
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
) -> dict[str, bool]:
    try:
        user_manager.reload()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reload users from the database",
        ) from exc
    return {"reloaded": True}
