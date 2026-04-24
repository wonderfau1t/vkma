from loguru import logger
from openai import BadRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AIService, AsyncVKApiClient
from app.database.crud import update_task
from app.database.models import TaskStatus, User


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
    except BadRequestError as e:
        error_code = e.body.get("error", {}).get("code") if isinstance(e.body, dict) else None
        if error_code == "no_images_generated":
            user = await db.get(User, user_id)
            if user:
                user.balance += cost
                await db.commit()
                logger.info(f"Баланс пользователя {user_id} возвращён: +{cost} (no_images_generated)")
            error_msg = "Не удалось сгенерировать изображение. Токены возвращены на баланс."
        else:
            error_msg = e.message
        await update_task(db, task_id, TaskStatus.FAILED, error_msg)
    except Exception as e:
        await update_task(db, task_id, TaskStatus.FAILED, str(e))
