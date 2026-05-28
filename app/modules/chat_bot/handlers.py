import asyncio
import random
import uuid

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clients import AIService, AsyncVKApiClient
from app.core.config import settings
from app.database.crud import (
    create_task,
    create_user,
    get_user_by_user_id,
    has_processing_tasks,
    update_task,
)
from app.database.models import GenerationTask, GenerationType, TaskStatus, User
from app.modules.analyzer import build_analysis_response, fetch_group_analysis
from app.modules.generator.costs import get_costs
from app.modules.generator.service import get_vk_user_profile, is_donut

from .keyboards import (
    generation_cancel_keyboard,
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


async def handle_message_async(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    """Обработчик входящих сообщений"""
    try:
        state = await get_user_state(user_id, redis_client)
        normalized_text = message_text.lower().strip()

        for handler in handlers:
            if handler["user_state"] == state and (
                handler["text"] is None or handler["text"] == normalized_text
            ):
                result = handler["func"](
                    user_id,
                    message_text,
                    vk_client,
                    redis_client,
                    ai_client,
                    db_session_factory,
                )
                if asyncio.iscoroutine(result):
                    await result
                return

        if state == "idle":
            await send_message(
                user_id,
                "Выберите действие в меню.",
                vk_client,
                main_menu_keyboard,
            )
    except Exception as exc:
        logger.exception(f"Ошибка обработки сообщения чат-бота для {user_id}: {exc}")
        await set_user_state(user_id, "idle", redis_client)
        await send_message(
            user_id,
            "Произошла ошибка. Попробуйте ещё раз или выберите действие в меню.",
            vk_client,
            main_menu_keyboard,
        )


async def _ensure_user(
    db: AsyncSession,
    user_id: int,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
) -> tuple[User, dict[str, int]]:
    costs = await get_costs(redis_client)
    user = await get_user_by_user_id(db, user_id)
    if user:
        if not user.avatar or user.full_name == f"Пользователь {user_id}":
            full_name, avatar = await get_vk_user_profile(vk_client, user_id)
            user.full_name = full_name
            user.avatar = avatar
            await db.commit()
        return user, costs

    full_name, avatar = await get_vk_user_profile(vk_client, user_id)
    try:
        is_now_donut = await is_donut(vk_client, settings.group_id, user_id)
    except Exception:
        is_now_donut = False

    balance = costs["donut_tokens"] if is_now_donut else costs["base_tokens"]
    user = await create_user(
        db,
        user_id,
        full_name=full_name,
        avatar=avatar,
        balance=balance,
        is_donut=is_now_donut,
    )
    return user, costs


async def _create_generation_task(
    db: AsyncSession,
    user: User,
    generation_type: GenerationType,
    prompt: str,
    cost: int,
) -> GenerationTask:
    user.balance -= cost
    return await create_task(
        db,
        str(uuid.uuid4()),
        generation_type,
        user.id,
        prompt,
    )


async def _refund_generation_cost(
    db_session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    task_id: str,
    cost: int,
    error: str,
) -> None:
    async with db_session_factory() as db:
        user = await db.get(User, user_id)
        if user:
            user.balance += cost
            await db.commit()
        await update_task(db, task_id, TaskStatus.FAILED, error)


async def _run_generation(
    user_id: int,
    prompt: str,
    generation_type: GenerationType,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as db:
        user, costs = await _ensure_user(db, user_id, vk_client, redis_client)
        task_in_progress = await has_processing_tasks(db, user_id)
        if task_in_progress:
            await send_message(
                user_id,
                "У вас уже есть задача в работе. Дождитесь результата и попробуйте снова.",
                vk_client,
                main_menu_keyboard,
            )
            return

        cost_key = "image" if generation_type == GenerationType.IMAGE else "post"
        generation_cost = costs[cost_key]
        if user.balance < generation_cost:
            await send_message(
                user_id,
                f"Недостаточно токенов на балансе. Нужно {generation_cost}, сейчас {user.balance}.",
                vk_client,
                main_menu_keyboard,
            )
            return

        task = await _create_generation_task(db, user, generation_type, prompt, generation_cost)

    await send_message(
        user_id,
        "Задача принята в работу. Вернусь с результатом, как только генерация завершится.",
        vk_client,
    )

    try:
        if generation_type == GenerationType.IMAGE:
            result, cost_rub = await ai_client.generate_image(prompt, task.id)
            result_message = f"Готово: https://vk.wonderrfau1t.site/images/{result}"
        else:
            result, cost_rub = await ai_client.generate_post(prompt, task.id)
            result_message = result

        async with db_session_factory() as db:
            await update_task(db, task.id, TaskStatus.SUCCESS, result, cost_rub)

        await send_message(user_id, result_message, vk_client, main_menu_keyboard)
    except Exception as exc:
        await _refund_generation_cost(
            db_session_factory,
            user_id,
            task.id,
            generation_cost,
            str(exc),
        )
        await send_message(
            user_id,
            "Не получилось выполнить генерацию. Токены вернул на баланс, попробуйте позже.",
            vk_client,
            main_menu_keyboard,
        )


@message_handler(user_state="idle", text="начать")
async def start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    response = (
        "Здравствуйте! Я помогу вам проверить оформление сообщества ВКонтакте "
        "по нескольким параметрам. Давайте начнем!"
    )
    await send_message(
        user_id=user_id,
        message=response,
        vk_client=vk_client,
        keyboard=main_menu_keyboard,
    )


@message_handler(user_state="idle", text="аудит сообщества")
@message_handler(user_state="idle", text="аудит")
async def audit_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
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
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    response = (
        'Выхожу из состояния аудита. Если хотите начать аудит сообщества, '
        'введите в любой момент команду "Аудит"'
    )
    await set_user_state(user_id, "idle", redis_client)
    await send_message(user_id, response, vk_client, main_menu_keyboard)


@message_handler(
    user_state="awaiting_link",
)
async def group_link_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    group_id = extract_group_id(message_text)
    if not group_id:
        await send_message(
            user_id,
            "Не удалось найти сообщество. Пожалуйста, убедитесь, что ссылка "
            "соответствует формату: https://vk.ru/… и повторите попытку",
            vk_client,
            to_main_menu_keyboard,
        )
        return

    group_info = await fetch_group_analysis(group_id, vk_client)
    if not group_info:
        await send_message(
            user_id,
            "Сообщество не найдено. Убедитесь, что ссылка верна и ведет "
            "на существующую группу ВКонтакте.",
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


@message_handler(user_state="idle", text="баланс")
async def balance_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as db:
        user, _ = await _ensure_user(db, user_id, vk_client, redis_client)

    await send_message(
        user_id,
        f"Ваш баланс: {user.balance} токенов.",
        vk_client,
        main_menu_keyboard,
    )


@message_handler(user_state="idle", text="генерация поста")
@message_handler(user_state="idle", text="пост")
async def post_generation_start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    await set_user_state(user_id, "awaiting_post_prompt", redis_client)
    await send_message(
        user_id,
        "Пришлите тему, тезисы или задачу для поста.",
        vk_client,
        generation_cancel_keyboard,
    )


@message_handler(user_state="idle", text="генерация изображения")
@message_handler(user_state="idle", text="изображение")
@message_handler(user_state="idle", text="картинка")
async def image_generation_start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    await set_user_state(user_id, "awaiting_image_prompt", redis_client)
    await send_message(
        user_id,
        "Опишите изображение, которое нужно сгенерировать.",
        vk_client,
        generation_cancel_keyboard,
    )


@message_handler(user_state="awaiting_post_prompt", text="отмена")
@message_handler(user_state="awaiting_image_prompt", text="отмена")
async def generation_cancel_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    await set_user_state(user_id, "idle", redis_client)
    await send_message(user_id, "Генерация отменена.", vk_client, main_menu_keyboard)


@message_handler(user_state="awaiting_post_prompt")
async def post_prompt_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    prompt = message_text.strip()
    if not prompt:
        await send_message(user_id, "Пришлите текстовый запрос для поста.", vk_client)
        return

    await set_user_state(user_id, "idle", redis_client)
    await _run_generation(
        user_id,
        prompt,
        GenerationType.POST,
        vk_client,
        redis_client,
        ai_client,
        db_session_factory,
    )


@message_handler(user_state="awaiting_image_prompt")
async def image_prompt_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    prompt = message_text.strip()
    if not prompt:
        await send_message(user_id, "Пришлите описание изображения.", vk_client)
        return

    await set_user_state(user_id, "idle", redis_client)
    await _run_generation(
        user_id,
        prompt,
        GenerationType.IMAGE,
        vk_client,
        redis_client,
        ai_client,
        db_session_factory,
    )
