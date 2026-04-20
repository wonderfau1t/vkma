from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis

from app.core.clients import AsyncVKApiClient
from app.core.config import settings
from app.dependencies import get_redis_client, get_vk_client

from .handlers import handle_message_sync

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=3)


@router.post("", response_class=PlainTextResponse)
async def vk_callback(
    request: Request,
    vk_client: AsyncVKApiClient = Depends(get_vk_client),
    redis_client: Redis = Depends(get_redis_client),
):
    data = await request.json()

    if data.get("type") == "confirmation":
        return settings.vk_group_confirmation_token.get_secret_value()

    elif data.get("type") == "message_new":
        user_id = data["object"]["message"]["from_id"]
        message_text = data["object"]["message"]["text"]
        attachments = data["object"]["message"]["attachments"]
        if attachments:
            executor.submit(
                handle_message_sync, user_id, attachments[0]["link"]["url"], vk_client, redis_client
            )
        else:
            executor.submit(handle_message_sync, user_id, message_text, vk_client, redis_client)
        return "ok"
