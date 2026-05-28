from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

from .auth import AdminTokenDep, login_admin
from .schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    UserBalanceUpdateRequest,
    UserBalanceUpdateResponse,
    UserDetailsResponse,
    UsersListResponse,
)
from .service import (
    get_user_details,
    get_users_page,
    update_user_balance as update_user_balance_service,
)

router = APIRouter()


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest):
    return login_admin(payload)


@router.get("/users", response_model=UsersListResponse)
async def get_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: AdminTokenDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "desc",
    is_donut: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
):
    return await get_users_page(
        db,
        limit=limit,
        offset=offset,
        sort_order=sort_order,
        is_donut=is_donut,
        search=search,
    )


@router.get("/users/{user_id}", response_model=UserDetailsResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: AdminTokenDep,
):
    return await get_user_details(db, user_id)


@router.post("/users/{user_id}/balance", response_model=UserBalanceUpdateResponse)
async def update_user_balance(
    user_id: int,
    payload: UserBalanceUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: AdminTokenDep,
):
    return await update_user_balance_service(db, user_id, payload)
