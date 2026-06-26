from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from vkbottle import API, Bot
from vkbottle.bot import Message
from vkbottle_types.events import GroupEventType

from app.core.clients import AIService, AsyncVKApiClient
from app.core.config import settings
from app.database.crud import create_user, get_user_by_user_id
from app.modules.generator.costs import get_costs

from .handlers import handle_message_async


class VKBottleClientAdapter:
    """Use VKBottle for bot methods and the existing client for service-token methods."""

    def __init__(self, api: API, fallback: AsyncVKApiClient) -> None:
        self.api = api
        self.fallback = fallback

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
        token: str | None = None,
    ) -> dict:
        return await self.fallback.get(endpoint, params or {}, token)

    async def post(
        self,
        endpoint: str,
        payload: dict | None = None,
        token: str | None = None,
    ) -> dict:
        if endpoint != "messages.send" or token is not None:
            return await self.fallback.post(endpoint, payload or {}, token)

        response = await self.api.request(endpoint, payload or {})
        return {"response": response}


@dataclass(slots=True)
class BotRuntime:
    vk_client: VKBottleClientAdapter
    redis_client: Redis
    ai_client: AIService
    db_session_factory: async_sessionmaker[AsyncSession]


bot = Bot(token=settings.vk_group_token.get_secret_value())
_runtime: BotRuntime | None = None


def configure_bot(
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    global _runtime
    _runtime = BotRuntime(
        vk_client=VKBottleClientAdapter(bot.api, vk_client),
        redis_client=redis_client,
        ai_client=ai_client,
        db_session_factory=db_session_factory,
    )


def _get_runtime() -> BotRuntime:
    if _runtime is None:
        raise RuntimeError("VKBottle runtime is not configured")
    return _runtime


def _message_text(message: Message) -> str:
    text = message.text
    if not message.attachments:
        return text

    link = getattr(message.attachments[0], "link", None)
    return getattr(link, "url", None) or text


@bot.on.message()
async def message_new_handler(message: Message) -> None:
    runtime = _get_runtime()
    await handle_message_async(
        message.from_id,
        _message_text(message),
        runtime.vk_client,
        runtime.redis_client,
        runtime.ai_client,
        runtime.db_session_factory,
    )


@bot.on.raw_event(
    [
        GroupEventType.DONUT_SUBSCRIPTION_CREATE,
        GroupEventType.DONUT_SUBSCRIPTION_PROLONGED,
    ],
)
async def donut_subscription_activated(event: dict[str, Any]) -> None:
    runtime = _get_runtime()
    event_type = event["type"]
    user_id = event["object"]["user_id"]

    async with runtime.db_session_factory() as db:
        costs = await get_costs(runtime.redis_client)
        user = await get_user_by_user_id(db, user_id)
        if not user:
            await create_user(
                db,
                user_id,
                balance=costs["donut_tokens"],
                is_donut=True,
            )
            return

        user.balance = costs["donut_tokens"]
        user.is_donut = True
        user.last_balance_reset_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info(
        f"Webhook: {event_type} для {user_id}. "
        f"Баланс {costs['donut_tokens']}, дата обновлена."
    )


@bot.on.raw_event(
    [
        GroupEventType.DONUT_SUBSCRIPTION_EXPIRED,
        GroupEventType.DONUT_SUBSCRIPTION_CANCELLED,
    ],
)
async def donut_subscription_deactivated(event: dict[str, Any]) -> None:
    runtime = _get_runtime()
    event_type = event["type"]
    user_id = event["object"]["user_id"]

    async with runtime.db_session_factory() as db:
        costs = await get_costs(runtime.redis_client)
        user = await get_user_by_user_id(db, user_id)
        if not user:
            return

        user.balance = costs["base_tokens"]
        user.is_donut = False
        user.last_balance_reset_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info(
        f"Webhook: {event_type} для {user_id}. "
        f"Баланс {costs['base_tokens']}, дата обновлена."
    )
