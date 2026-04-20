from fastapi import Request
from redis.asyncio import Redis

from app.core.clients import AIService, AsyncVKApiClient


def get_vk_client(request: Request) -> AsyncVKApiClient:
    return request.app.state.vk_client


def get_ai_client(request: Request) -> AIService:
    return request.app.state.ai_client


def get_redis_client(request: Request) -> Redis:
    return request.app.redis_client
