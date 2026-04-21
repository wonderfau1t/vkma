from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AIService, AsyncVKApiClient


def get_vk_client(request: Request) -> AsyncVKApiClient:
    return request.app.state.vk_client


def get_ai_client(request: Request) -> AIService:
    return request.app.state.ai_client


def get_redis_client(request: Request) -> Redis:
    return request.app.state.redis_client


async def get_db(request: Request):
    # Мы итерируемся по генератору и отдаем сессию дальше
    async for session in request.app.state.db.session_getter():
        yield session
