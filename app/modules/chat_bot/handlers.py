import asyncio
import random

from redis.asyncio import Redis

from app.core.clients import AsyncVKApiClient
from app.modules.analyzer import build_analysis_response, fetch_group_analysis

from .keyboards import (
    inline_group_analysis_keyboard,
    inline_main_menu_keyboard,
    main_menu_keyboard,
    to_main_menu_keyboard,
)
from .utils import (
    extract_group_id,
    generate_message_text,
    get_user_state,
    send_message,
    set_user_state,
)

handlers = []


def message_handler(user_state=None, text=None):
    """Декоратор для регистрации обработчиков сообщений"""

    def decorator(func):
        handlers.append(
            {
                "user_state": user_state,
                "text": text,
                "func": func,
            }
        )
        return func

    return decorator


def handle_message_sync(user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis):
    loop = asyncio.get_event_loop()  # или asyncio.new_event_loop()
    coro = handle_message_async(user_id, message_text, vk_client, redis_client)  # переименуй текущий в _async
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.result()  # ждём завершения


async def handle_message_async(
    user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis
):
    """Обработчик входящих сообщений"""
    state = await get_user_state(user_id, redis_client)

    for handler in handlers:
        if handler["user_state"] == state and (
            handler["text"] is None or handler["text"] == message_text.lower()
        ):
            result = handler["func"](user_id, message_text, vk_client, redis_client)
            if asyncio.iscoroutine(result):
                await result
            return


@message_handler(user_state="idle", text="начать")
async def start_handler(
    user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis
):
    response = "Здравствуйте! Я помогу вам проверить оформление сообщества ВКонтакте по нескольким параметрам. Давайте начнем!"
    await send_message(user_id=user_id, message=response, vk_client=vk_client)


@message_handler(user_state="idle", text="аудит сообщества")
@message_handler(user_state="idle", text="аудит")
async def audit_handler(
    user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis
):
    await send_message(
        user_id=user_id,
        message="Бот переходит в режим аудита",
        vk_client=vk_client,
        keyboard=to_main_menu_keyboard,
    )

    response = "Для аудита пришлите, пожалуйста, ссылку на сообщество, которое хотите проверить."
    await set_user_state(user_id, "awaiting_link", redis_client)
    await send_message(
        user_id=user_id,
        message=response,
        vk_client=vk_client,
        keyboard=inline_group_analysis_keyboard,
    )


@message_handler(user_state="awaiting_link", text="выйти из аудита")
async def main_menu_handler(
    user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis
):
    response = 'Выхожу из состояния аудита. Если хотите начать аудит сообщества, введите в любой момент команду "Аудит"'
    await set_user_state(user_id, "idle", redis_client)
    await send_message(user_id, response, vk_client, main_menu_keyboard)


@message_handler(
    user_state="awaiting_link",
)
async def group_link_handler(
    user_id: int, message_text: str, vk_client: AsyncVKApiClient, redis_client: Redis
):
    group_id = extract_group_id(message_text)
    if not group_id:
        await send_message(
            user_id,
            "Не удалось найти сообщество. Пожалуйста, убедитесь, что ссылка соответствует формату: https://vk.ru/… и повторите попытку",
            vk_client,
            to_main_menu_keyboard,
        )
        return

    group_info = await fetch_group_analysis(group_id, vk_client)
    if not group_info:
        await send_message(
            user_id,
            "Сообщество не найдено. Убедитесь, что ссылка верна и ведет на существующую группу ВКонтакте.",
            vk_client,
            to_main_menu_keyboard,
        )
        return

    api_response = build_analysis_response(group_info)
    response_messages = generate_message_text(api_response)

    await asyncio.sleep(random.randint(5, 8))

    pivot = len(response_messages) // 2
    await send_message(user_id, "".join(response_messages[:pivot]), vk_client)
    await send_message(user_id, "".join(response_messages[pivot:]), vk_client, main_menu_keyboard)
    await send_message(
        user_id,
        '🔎 Если хотите проанализировать другое сообщество, то нажмите на "Аудит сообщества"',
        vk_client,
        inline_main_menu_keyboard,
    )
    await set_user_state(user_id, "idle", redis_client)
