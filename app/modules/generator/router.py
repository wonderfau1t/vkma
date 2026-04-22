import asyncio
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AIService, AsyncVKApiClient
from app.core.clients.vk_api.auth import VKVerifiedTokenDep
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
from app.dependencies import get_ai_client, get_db, get_vk_client

from .models import GenerateRequest
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
    try:
        is_now_donut = await is_donut(vk_client, settings.group_id, user_id)
        if is_now_donut:
            if not user.is_donut:
                user.balance = 1000
                user.is_donut = True
                await db.commit()
                logger.info(f"Пользователь {user_id} стал доном. Баланс обновлен до 1000.")
        else:
            if user.is_donut:
                user.balance = 30
                user.is_donut = False
                await db.commit()
                logger.info(f"Пользователь {user_id} перестал быть доном. Баланс сброшен до 30.")

        return {
            "balance": user.balance,
            "isDonut": user.is_donut,
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке Donut для {user_id}: {e}")

    return {
        "balance": user.balance,
        "isDonut": user.is_donut,
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
    if task.status == TaskStatus.PROCESSING or task.status == TaskStatus.FAILED:
        return {"status": task.status}
    return {
        "status": task.status,
        "result": f"https://vk.wonderrfau1t.site/images/{task.result}"
        if task.type == GenerationType.IMAGE
        else task.result,
    }


@router.post("/generate")
async def generate(
    data: GenerateRequest,
    user_id: VKVerifiedTokenDep,
    db: AsyncSession = Depends(get_db),
    ai_client: AIService = Depends(get_ai_client),
):
    # Существует ли пользователь
    user = await get_user_by_user_id(db, user_id)
    if not user:
        logger.error(f"Попытка генерации несуществующим пользователем: {user_id}")
        raise HTTPException(status_code=404, detail="Клиент не найден")

    generation_cost = 10 if data.type == "image" else 2

    # Достаточно баланса?
    if user.balance < generation_cost:
        logger.info(
            f"Недостаточно средств у {user_id}: нужно {generation_cost}, есть {user.balance}"
        )
        return {"message": "Недостаточно токенов на балансе"}

    task_id = str(uuid.uuid4())
    gen_type = GenerationType.IMAGE if data.type == "image" else GenerationType.POST

    try:
        user.balance -= generation_cost
        await create_task(
            db,
            task_id,
            gen_type,
            user_id,
            data.prompt,
        )
        await db.commit()

        logger.info(
            f"Задача {task_id} создана ({gen_type}). Списано {generation_cost} токенов у {user_id}"
        )

        asyncio.create_task(process_generation(ai_client, db, gen_type, task_id, data.prompt))

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
            "createdAt": task.created_at,
            "prompt": task.prompt,
            "result": f"https://vk.wonderrfau1t.site/images/{task.result}"
            if task.type == GenerationType.IMAGE
            else task.result,
        }
        for task in tasks
    ]

    return {"count": len(items), "items": items}


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
