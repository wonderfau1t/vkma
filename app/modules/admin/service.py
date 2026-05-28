from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ActionType, User, UserLogs

from .schemas import (
    LogsListItem,
    UserBalanceUpdateRequest,
    UserBalanceUpdateResponse,
    UserDetailsResponse,
    UsersListItem,
    UsersListMeta,
    UsersListResponse,
)


def _build_user_item(user: User) -> UsersListItem:
    return UsersListItem(
        id=user.id,
        avatar=user.avatar or "",
        full_name=f"Пользователь {user.id}",
        registered_at=user.registered_at,
        is_donut=user.is_donut,
        balance=user.balance,
    )


async def get_users_page(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> UsersListResponse:
    query = (
        select(User)
        .order_by(User.registered_at.desc(), User.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )

    result = await db.execute(query)
    users = list(result.scalars().all())
    has_more = len(users) > limit
    page_users = users[:limit]

    items = [
        UsersListItem(
            id=user.id,
            avatar=user.avatar or "",
            full_name=user.full_name,
            registered_at=user.registered_at,
            is_donut=user.is_donut,
            balance=user.balance,
        )
        for user in page_users
    ]

    return UsersListResponse(
        items=items,
        meta=UsersListMeta(limit=limit, offset=offset, has_more=has_more),
    )


async def get_user_details(
    db: AsyncSession,
    user_id: int,
) -> UserDetailsResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    logs_result = await db.execute(
        select(UserLogs)
        .where(UserLogs.user_id == user.id)
        .order_by(UserLogs.created_at.desc(), UserLogs.id.desc())
    )
    logs = [
        LogsListItem(
            id=log.id,
            action=log.action,
            amount=log.amount,
            change=log.change,
            comment=log.comment,
            datetime=log.created_at,
        )
        for log in logs_result.scalars().all()
    ]

    return UserDetailsResponse(
        **UsersListItem(
            id=user.id,
            avatar=user.avatar or "",
            full_name=user.full_name,
            registered_at=user.registered_at,
            is_donut=user.is_donut,
            balance=user.balance,
        ).model_dump(),
        last_balance_reset_at=user.last_balance_reset_at,
        logs=logs,
    )


async def update_user_balance(
    db: AsyncSession,
    user_id: int,
    payload: UserBalanceUpdateRequest,
) -> UserBalanceUpdateResponse:
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    previous_balance = user.balance

    if payload.action == "increase":
        new_balance = previous_balance + payload.amount
    elif payload.action == "decrease":
        new_balance = previous_balance - payload.amount
    else:
        new_balance = payload.amount

    if new_balance < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Баланс не может быть отрицательным",
        )

    user.balance = new_balance
    db.add(
        UserLogs(
            user_id=user.id,
            action=ActionType(payload.action),
            amount=payload.amount,
            change=f"{previous_balance} -> {new_balance}",
            comment=payload.comment or "",
        )
    )

    await db.commit()
    await db.refresh(user)

    return UserBalanceUpdateResponse(balance=user.balance)
