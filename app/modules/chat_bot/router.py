from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients import AsyncVKApiClient
from app.core.config import settings
from app.dependencies import get_db, get_redis_client, get_vk_client
from app.database.crud import get_user_by_user_id, create_user

from .handlers import handle_message_sync

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=3)


@router.post("", response_class=PlainTextResponse)
async def vk_callback(
    request: Request,
    vk_client: AsyncVKApiClient = Depends(get_vk_client),
    redis_client: Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db)
):
    data = await request.json()

    event_type = data.get("type")
    obj = data.get("object", {})
    user_id = obj.get("user_id")

    if event_type == "confirmation":
        return settings.vk_group_confirmation_token.get_secret_value()

    elif event_type == "message_new":
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

    elif event_type in ["donut_subscription_create", "donut_subscription_prolonged"]:
        user = await get_user_by_user_id(db, user_id)
        if not user:
            await create_user(db, user_id)
            return
        user.balance = 1000
        user.is_donut = True
        await db.commit()
    
    elif event_type in ["donut_subscription_expired", "donut_subscription_cancelled"]:
        user = await get_user_by_user_id(db, user_id)
        if not user:
            await create_user(db, user_id)
            return
        user.balance = 30
        user.is_donut = False
        await db.commit()
    