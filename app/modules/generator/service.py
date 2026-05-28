from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AIService, AsyncVKApiClient
from app.core.config import settings
from app.database.crud import update_task
from app.database.models import TaskStatus, User


async def get_vk_user_profile(vk_client: AsyncVKApiClient, user_id: int) -> tuple[str, str]:
    fallback_name = f"Пользователь {user_id}"

    try:
        response = await vk_client.get(
            "users.get",
            {
                "user_ids": str(user_id),
                "fields": "photo_100",
            },
            token=settings.vk_service_token.get_secret_value(),
        )
    except Exception as exc:
        logger.warning(f"Не удалось получить профиль VK для {user_id}: {exc}")
        return fallback_name, ""

    profiles = response.get("response", [])
    if not profiles:
        return fallback_name, ""

    profile = profiles[0]
    first_name = profile.get("first_name", "")
    last_name = profile.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or fallback_name
    avatar = profile.get("photo_100") or ""

    return full_name, avatar


async def is_donut(vk_client: AsyncVKApiClient, group_id: int, user_id: int):
    response = await vk_client.get(
        "groups.getMembers",
        {
            "group_id": group_id,
            "filter": "donut",
        },
    )
    subs = response.get("response", {}).get("items", [])
    if user_id in subs:
        return True
    return False


async def process_generation(
    client: AIService,
    db: AsyncSession,
    generation_type: str,
    task_id: str,
    prompt: str,
    reference_image: bytes | None = None,
    aspect_ratio: str | None = None,
    user_id: int = 0,
    cost: int = 0,
):
    try:
        if generation_type == "image":
            result, cost_rub = await client.generate_image(
                prompt, task_id, reference_image=reference_image, aspect_ratio=aspect_ratio
            )
        else:
            result, cost_rub = await client.generate_post(prompt, task_id)
        await update_task(db, task_id, TaskStatus.SUCCESS, result, cost_rub)
    except Exception as e:
        logger.error(f"Ошибка генерации [{task_id}]: {e}")
        user = await db.get(User, user_id)
        if user:
            user.balance += cost
            await db.commit()
            logger.info(f"Баланс пользователя {user_id} возвращён: +{cost}")
        await update_task(db, task_id, TaskStatus.FAILED, str(e))
