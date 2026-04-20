from typing import Literal

from fastapi import APIRouter

from .models import GenerateRequest

router = APIRouter()


@router.get("/balance")
async def get_balance():
    return {
        "balance": 1000,
        "isDon": True,
    }


@router.get("/tasks")
async def get_tasks():
    return {
        "status": "ready, если нет задач в работе. taskInWork, если есть таска в работе",
        "taskId": "id задачи, которая в работе",
    }


@router.get("/tasks/{task_id}")
async def get_task_by_id(task_id: str):
    return {"status": "completed, cancelled, pending", "result": "если статус completed"}


@router.post("/generate")
async def generate(data: GenerateRequest):
    return {"taskId": "67-228-52"}


@router.get("/history")
async def get_history(type: Literal["posts", "images"]):
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
