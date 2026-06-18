from typing import Literal

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ActionType,
    GenerationTask,
    GenerationType,
    TaskStatus,
    User,
    UserLogs,
)
from app.modules.generator.costs import get_costs, set_costs

from .schemas import (
    GenerationHistoryItem,
    GenerationSettingsResponse,
    GenerationSettingsUpdateRequest,
    LogsListItem,
    UserBalanceUpdateRequest,
    UserBalanceUpdateResponse,
    UserDetailsResponse,
    UsersListItem,
    UsersListMeta,
    UsersListResponse,
)

IMAGE_RESULT_BASE_URL = "https://vk.wonderrfau1t.site/images"


def _build_generation_settings_response(settings: dict[str, int]) -> GenerationSettingsResponse:
    return GenerationSettingsResponse(
        base_tokens=settings["base_tokens"],
        donut_tokens=settings["donut_tokens"],
        post_cost=settings["post"],
        image_cost=settings["image"],
    )


async def get_generation_settings(redis: Redis) -> GenerationSettingsResponse:
    settings = await get_costs(redis)
    return _build_generation_settings_response(settings)


async def update_generation_settings(
    redis: Redis,
    payload: GenerationSettingsUpdateRequest,
) -> GenerationSettingsResponse:
    settings = await set_costs(
        redis,
        image=payload.image_cost,
        post=payload.post_cost,
        base_tokens=payload.base_tokens,
        donut_tokens=payload.donut_tokens,
    )
    return _build_generation_settings_response(settings)


def _build_user_item(user: User) -> UsersListItem:
    return UsersListItem(
        id=user.id,
        avatar=user.avatar or "",
        full_name=user.full_name,
        registered_at=user.registered_at,
        is_donut=user.is_donut,
        balance=user.balance,
    )


async def get_users_page(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    sort_order: Literal["asc", "desc"] = "desc",
    is_donut: bool | None = None,
    search: str | None = None,
) -> UsersListResponse:
    query = select(User)

    if is_donut is not None:
        query = query.where(User.is_donut == is_donut)

    if search:
        search_value = search.strip()
        if search_value:
            conditions = [User.full_name.ilike(f"%{search_value}%")]
            if search_value.isdigit():
                conditions.append(User.id == int(search_value))
            query = query.where(or_(*conditions))

    if sort_order == "asc":
        query = query.order_by(User.registered_at.asc(), User.id.asc())
    else:
        query = query.order_by(User.registered_at.desc(), User.id.desc())

    query = query.offset(offset).limit(limit + 1)

    result = await db.execute(query)
    users = list(result.scalars().all())
    has_more = len(users) > limit
    page_users = users[:limit]

    items = [_build_user_item(user) for user in page_users]

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

    tasks_result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.user_id == user.id)
        .order_by(GenerationTask.created_at.desc(), GenerationTask.id.desc())
    )
    generation_history = []
    for task in tasks_result.scalars().all():
        is_success = task.status == TaskStatus.SUCCESS
        is_failed = task.status == TaskStatus.FAILED
        result = task.result if is_success else None
        if result and task.type == GenerationType.IMAGE:
            result = f"{IMAGE_RESULT_BASE_URL}/{result}"

        generation_history.append(
            GenerationHistoryItem(
                id=task.id,
                prompt=task.prompt,
                datetime=task.created_at,
                type=task.type,
                status=task.status,
                cost_rub=task.cost_rub,
                result=result,
                error=task.result if is_failed else None,
            )
        )

    return UserDetailsResponse(
        **_build_user_item(user).model_dump(),
        last_balance_reset_at=user.last_balance_reset_at,
        logs=logs,
        generation_history=generation_history,
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
