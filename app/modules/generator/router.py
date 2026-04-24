import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from typing import Literal

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AIService, AsyncVKApiClient
from app.core.clients.vk_api.auth import AdminSecretDep, VKVerifiedTokenDep
from app.core.config import settings
from app.database.crud import (
    create_task,
    create_user,
    get_history_by_type,
    get_task_by_task_id,
    get_user_by_user_id,
    has_processing_tasks,
)
from app.database.models import GenerationType, TaskStatus
from app.dependencies import get_ai_client, get_db, get_redis_client, get_vk_client

from .costs import get_costs, set_costs
from .models import GenerateRequest, UpdateCostsRequest
from .service import is_donut, process_generation

router = APIRouter()


@router.get("/balance")
async def get_balance(
    user_id: VKVerifiedTokenDep,
    db: AsyncSession = Depends(get_db),
    vk_client: AsyncVKApiClient = Depends(get_vk_client),
):
    user = await get_user_by_user_id(db, user_id)
    if not user:
        user = await create_user(db, user_id)
        logger.info(f"Создан новый пользователь: {user_id}")

    now = datetime.now(timezone.utc)
    # Порог обновления (30 дней)
    is_time_to_reset = user.last_reset_at is None or (now - user.last_reset_at) >= timedelta(days=30)

    try:
        # Получаем актуальный статус из VK
        is_now_donut = await is_donut(vk_client, settings.group_id, user_id)
        
        # Определяем, изменился ли статус по сравнению с базой
        status_changed = is_now_donut != user.is_donut
        
        # ЛОГИКА ОБНОВЛЕНИЯ
        if status_changed or is_time_to_reset:
            # Определяем новый лимит
            new_balance = 1000 if is_now_donut else 30
            
            user.balance = new_balance
            user.is_donut = is_now_donut
            user.last_reset_at = now
            
            await db.commit()
            
            reason = "смена статуса" if status_changed else "плановое обновление (30 дней)"
            logger.info(f"Баланс пользователя {user_id} обновлен до {new_balance} ({reason})")

    except Exception as e:
        logger.error(f"Ошибка при проверке баланса для {user_id}: {e}")

    return {
        "balance": user.balance,
        "isDonut": user.is_donut,
        "nextResetAt": (user.last_reset_at + timedelta(days=30)) if user.last_reset_at else None
    }


@router.get("/tasks")
async def get_tasks(
    user_id: VKVerifiedTokenDep,
    db: AsyncSession = Depends(get_db),
):
    task = await has_processing_tasks(db, user_id)
    if not task:
        return {"status": "ready"}

    return {
        "status": "not ready",
        "taskId": task.id,
        "type": task.type,
        "prompt": task.prompt,
    }


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str, db: AsyncSession = Depends(get_db)):
    task = await get_task_by_task_id(db, task_id=task_id)
    if not task:
        logger.warning(f"Запрос несуществующей задачи: {task_id}")
        return {"status": "not_found"}
    if task.status == TaskStatus.PROCESSING:
        return {"status": task.status}
    if task.status == TaskStatus.FAILED:
        return {"status": task.status, "errorMessage": task.result}
    return {
        "status": task.status,
        "result": f"https://vk.wonderrfau1t.site/images/{task.result}"
        if task.type == GenerationType.IMAGE
        else task.result,
    }


@router.post("/generate")
async def generate(
    type: Annotated[Literal["image", "post"], Form()],
    prompt: Annotated[str, Form()],
    user_id: VKVerifiedTokenDep,
    aspect_ratio: Annotated[str | None, Form()] = None,
    reference_image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    ai_client: AIService = Depends(get_ai_client),
    redis_client: Redis = Depends(get_redis_client),
):
    # Существует ли пользователь
    user = await get_user_by_user_id(db, user_id)
    if not user:
        logger.error(f"Попытка генерации несуществующим пользователем: {user_id}")
        raise HTTPException(status_code=404, detail="Клиент не найден")

    costs = await get_costs(redis_client)
    generation_cost = costs[type]

    # Достаточно баланса?
    if user.balance < generation_cost:
        logger.info(
            f"Недостаточно средств у {user_id}: нужно {generation_cost}, есть {user.balance}"
        )
        return {"message": "Недостаточно токенов на балансе"}

    task_id = str(uuid.uuid4())
    gen_type = GenerationType.IMAGE if type == "image" else GenerationType.POST
    image_bytes = await reference_image.read() if reference_image else None

    try:
        user.balance -= generation_cost
        await create_task(
            db,
            task_id,
            gen_type,
            user_id,
            prompt,
        )
        await db.commit()

        logger.info(
            f"Задача {task_id} создана ({gen_type}). Списано {generation_cost} токенов у {user_id}"
        )

        asyncio.create_task(
            process_generation(
                ai_client, db, gen_type, task_id, prompt, image_bytes, aspect_ratio,
                user_id=user_id, cost=generation_cost,
            )
        )

    except Exception as e:
        await db.rollback()
        logger.exception(f"Ошибка при создании задачи генерации для {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    # Ответ пользователю с id задачи
    return {"taskId": task_id}


@router.get("/history")
async def get_history(
    user_id: VKVerifiedTokenDep,
    task_type: Literal["posts", "images"],
    db: AsyncSession = Depends(get_db),
):
    tasks = await get_history_by_type(
        db,
        GenerationType.IMAGE if task_type == "images" else GenerationType.POST,
        user_id,
    )

    if not tasks:
        return {"count": 0, "items": []}

    items = [
        {
            "id": task.id,
            "createdAt": task.created_at.strftime("%H:%M %d.%m.%Y"),
            "prompt": task.prompt,
            "result": f"https://vk.wonderrfau1t.site/images/{task.result}"
            if task.type == GenerationType.IMAGE
            else task.result,
        }
        for task in tasks
    ]

    return {"count": len(items), "items": items}


@router.get("/costs")
async def get_generation_costs(redis_client: Redis = Depends(get_redis_client)):
    return await get_costs(redis_client)


@router.patch("/costs")
async def update_generation_costs(
    data: UpdateCostsRequest,
    _: AdminSecretDep,
    redis_client: Redis = Depends(get_redis_client),
):
    await set_costs(redis_client, image=data.image, post=data.post)
    logger.info(f"Стоимость генерации обновлена: image={data.image}, post={data.post}")
    return {"image": data.image, "post": data.post}


@router.get("/balance-fake")
async def fake_get_balance(session: AsyncSession = Depends(get_db)):
    logger.warning("ВОРНИНГ")
    return {
        "balance": 1000,
        "isDon": True,
    }


@router.get("/tasks-fake")
async def fake_get_tasks():
    return {
        "status": "ready, если нет задач в работе. taskInWork, если есть таска в работе",
        "taskId": "id задачи, которая в работе",
    }


@router.post("/generate-fake")
async def fake_generate(data: GenerateRequest):
    return {"taskId": "67-228-52"}


@router.get("/history-fake")
async def fake_get_history(type: Literal["posts", "images"]):
    return {
        "count": 144,
        "items": [
            {
                "id": 52,
                "date": "дата",
                "prompt": "текст промпта",
                "result": "либо текст, либо ссылка на картинку",
            },
            {
                "id": 76,
                "date": "дата",
                "prompt": "текст промпта",
                "result": "либо текст, либо ссылка на картинку",
            },
        ],
    }
