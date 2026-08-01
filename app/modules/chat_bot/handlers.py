import asyncio
import inspect
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
    empty_keyboard,
    generation_cancel_keyboard,
    image_aspect_ratio_keyboard,
    main_menu_keyboard,
    to_main_menu_keyboard,
)
from .states import UserState
from .utils import (
    MAX_IMAGE_REFERENCES,
    clear_image_generation_context,
    extract_group_id,
    extract_photo_urls,
    generate_message_text,
    get_image_prompt,
    get_image_references,
    get_user_state,
    save_image_prompt,
    save_image_references,
    send_message,
    set_user_state,
)

handlers = []
IMAGE_ASPECT_RATIOS = {
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "4:5",
    "5:4",
    "3:2",
    "2:3",
    "21:9",
}


def message_handler(user_state: UserState | None = None, text: str | None = None):
    """Декоратор для регистрации обработчиков сообщений"""

    def decorator(func):
        handlers.append(
            {
                "user_state": user_state,
                "text": text,
                "func": func,
                "accepts_attachments": "attachments" in inspect.signature(func).parameters,
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
    attachments: list[dict] | None = None,
):
    """Обработчик входящих сообщений"""
    try:
        state = await get_user_state(user_id, redis_client)
        normalized_text = message_text.lower().strip()

        if normalized_text == "стоп":
            await clear_image_generation_context(user_id, redis_client)
            await set_user_state(user_id, UserState.INACTIVE, redis_client)
            await send_message(
                user_id,
                "Договорились, Останавливаюсь! 👌😊 Если будет нужна помощь, просто напишите: Привет, Ваня!",
                vk_client,
                empty_keyboard,
            )
            return

        for handler in handlers:
            state_matches = handler["user_state"] is None or handler["user_state"] == state
            if state_matches and (handler["text"] is None or handler["text"] == normalized_text):
                args = [
                    user_id,
                    message_text,
                    vk_client,
                    redis_client,
                    ai_client,
                    db_session_factory,
                ]
                if handler["accepts_attachments"]:
                    args.append(attachments)
                result = handler["func"](*args)
                if asyncio.iscoroutine(result):
                    await result
                return

        if state == UserState.IDLE:
            await send_message(
                user_id,
                "Выберите действие в меню.",
                vk_client,
                main_menu_keyboard,
            )
    except Exception as exc:
        logger.exception(f"Ошибка обработки сообщения чат-бота для {user_id}: {exc}")
        await set_user_state(user_id, UserState.IDLE, redis_client)
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


async def _ensure_can_start_generation(
    user_id: int,
    generation_type: GenerationType,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> bool:
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
            return False

        cost_key = "image" if generation_type == GenerationType.IMAGE else "post"
        generation_cost = costs[cost_key]
        if user.balance < generation_cost:
            await send_message(
                user_id,
                f"Недостаточно токенов на балансе. Нужно {generation_cost}, сейчас {user.balance}.",
                vk_client,
                main_menu_keyboard,
            )
            return False

    return True


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
    reference_images: list[bytes] | None = None,
    aspect_ratio: str | None = None,
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
            result, cost_rub = await ai_client.generate_image(
                prompt,
                task.id,
                reference_image=reference_images,
                aspect_ratio=aspect_ratio,
            )
            result_message = f"Готово: https://api.lesyatarget.ru/images/{result}"
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


@message_handler(text="привет, ваня")
@message_handler(text="привет, ваня!")
@message_handler(text="привет ваня!")
@message_handler(text="привет ваня")
@message_handler(text="начать")
async def start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    await clear_image_generation_context(user_id, redis_client)
    await set_user_state(user_id, UserState.IDLE, redis_client)
    response = (
        "Привет 👋 Меня зовут Ваня, я Ai-помощник по контенту.\n\n"
        "Помогу вам проверить 🔍 оформление сообщества ВКонтакте и сгенерирую контент для вашей аудитории (Напишу посты и изображения)\n\n"
        "Давайте начнем?! Пожалуйста, выберите интересующий пункт 👇"
    )
    await send_message(
        user_id=user_id,
        message=response,
        vk_client=vk_client,
        keyboard=main_menu_keyboard,
    )


@message_handler(user_state=UserState.IDLE, text="аудит сообщества")
@message_handler(user_state=UserState.IDLE, text="аудит")
async def audit_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    # await send_message(
    #     user_id=user_id,
    #     message="Бот переходит в режим аудита",
    #     vk_client=vk_client,
    #     keyboard=to_main_menu_keyboard,
    # )

    response = "🔍 Перехожу в режим аудита. Пожалуйста, пришлите ссылку на ваше сообщество, которое хотите проверить."
    await set_user_state(user_id, UserState.AWAITING_LINK, redis_client)
    await send_message(
        user_id=user_id,
        message=response,
        vk_client=vk_client,
        keyboard=to_main_menu_keyboard,
    )


@message_handler(user_state=UserState.AWAITING_LINK, text="назад")
async def main_menu_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    response = "Возвращаюсь назад"
    await set_user_state(user_id, UserState.IDLE, redis_client)
    await send_message(user_id, response, vk_client, main_menu_keyboard)


@message_handler(
    user_state=UserState.AWAITING_LINK,
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
    await send_message(user_id, "".join(response_messages[pivot:]), vk_client)
    await send_message(
        user_id,
        "Выберите следующий интересующий пункт 👇",
        vk_client,
        main_menu_keyboard,
    )
    await set_user_state(user_id, UserState.IDLE, redis_client)


@message_handler(user_state=UserState.IDLE, text="баланс")
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


@message_handler(user_state=UserState.IDLE, text="генерация поста")
@message_handler(user_state=UserState.IDLE, text="пост")
async def post_generation_start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    if not await _ensure_can_start_generation(
        user_id,
        GenerationType.POST,
        vk_client,
        redis_client,
        db_session_factory,
    ):
        return

    await set_user_state(user_id, UserState.AWAITING_POST_PROMPT, redis_client)
    await send_message(
        user_id,
        "Ваня готов к работе 😎 На какую тему будем писать? ✍\n\nЧтобы я подготовил пост, задайте правильный промт в формате:\n\n"
        'Роль (ты опытный специалист в..)+ Задача (напиши пост на тему...)+ Стиль и ограничения (Дружелюбный/официальный и др, не используй слова ***, избегай банальных советов вроде "просто начни" и т.п.) + критерии хорошего результата (Опишите, каким должен быть итоговый текст: Экспертный, продающий, с цепляющим заголовком, с призывом к действию/вопросом).',
        vk_client,
        generation_cancel_keyboard,
    )


@message_handler(user_state=UserState.IDLE, text="генерация изображения")
@message_handler(user_state=UserState.IDLE, text="изображение")
@message_handler(user_state=UserState.IDLE, text="картинка")
async def image_generation_start_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    if not await _ensure_can_start_generation(
        user_id,
        GenerationType.IMAGE,
        vk_client,
        redis_client,
        db_session_factory,
    ):
        return

    await clear_image_generation_context(user_id, redis_client)
    await set_user_state(user_id, UserState.AWAITING_IMAGE_PROMPT, redis_client)
    await send_message(
        user_id,
        "Ваня готов к работе 😎 Что будем создавать?\n\n"
        "📸 Чтобы я подготовил для вас изображение, задайте правильный промт в формате:\n\n"
        "[Что изображено] + [Стиль] + [Цвета] + [Композиция/Расположение объектов] + [Текст, если нужен]. "
        "Можно прикрепить до 3 фото-референсов — одним сообщением или по очереди. "
        "Соотношение сторон выберете следующим шагом.",
        vk_client,
        generation_cancel_keyboard,
    )


@message_handler(user_state=UserState.AWAITING_POST_PROMPT, text="назад")
@message_handler(user_state=UserState.AWAITING_IMAGE_PROMPT, text="назад")
@message_handler(user_state=UserState.AWAITING_IMAGE_ASPECT_RATIO, text="назад")
async def generation_cancel_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    await clear_image_generation_context(user_id, redis_client)
    await set_user_state(user_id, UserState.IDLE, redis_client)
    await send_message(user_id, "Возращаюсь назад", vk_client, main_menu_keyboard)


@message_handler(user_state=UserState.AWAITING_POST_PROMPT)
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

    await set_user_state(user_id, UserState.IDLE, redis_client)
    await _run_generation(
        user_id,
        prompt,
        GenerationType.POST,
        vk_client,
        redis_client,
        ai_client,
        db_session_factory,
    )


@message_handler(user_state=UserState.AWAITING_IMAGE_PROMPT)
async def image_prompt_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
    attachments: list[dict] | None = None,
):
    prompt = message_text.strip()
    stored_references = await get_image_references(user_id, redis_client)
    photo_urls = extract_photo_urls(attachments)

    if len(stored_references) + len(photo_urls) > MAX_IMAGE_REFERENCES:
        await send_message(
            user_id,
            f"Можно прикрепить не более {MAX_IMAGE_REFERENCES} референсов. "
            f"Сейчас сохранено: {len(stored_references)}.",
            vk_client,
            generation_cancel_keyboard,
        )
        return

    if photo_urls:
        downloaded_references = list(
            await asyncio.gather(*(vk_client.download(url) for url in photo_urls))
        )
        if any(len(image) > 20 * 1024 * 1024 for image in downloaded_references):
            await send_message(
                user_id,
                "Одно из фото слишком большое. Каждое изображение должно быть до 20 МБ.",
                vk_client,
                generation_cancel_keyboard,
            )
            return
        reference_count = await save_image_references(
            user_id,
            downloaded_references,
            redis_client,
        )
    else:
        reference_count = len(stored_references)

    if not prompt:
        if reference_count:
            await send_message(
                user_id,
                f"Референсы получил: {reference_count}/{MAX_IMAGE_REFERENCES} 👍 "
                "Можете добавить ещё или прислать текстовое описание изображения.",
                vk_client,
                generation_cancel_keyboard,
            )
        else:
            await send_message(
                user_id,
                "Пришлите описание изображения и, при необходимости, фото-референс.",
                vk_client,
                generation_cancel_keyboard,
            )
        return

    await save_image_prompt(user_id, prompt, redis_client)
    await set_user_state(
        user_id,
        UserState.AWAITING_IMAGE_ASPECT_RATIO,
        redis_client,
    )
    await send_message(
        user_id,
        "Выберите соотношение сторон будущего изображения 👇\n"
        "«Авто» — модель выберет формат самостоятельно.",
        vk_client,
        image_aspect_ratio_keyboard,
    )


@message_handler(user_state=UserState.AWAITING_IMAGE_ASPECT_RATIO)
async def image_aspect_ratio_handler(
    user_id: int,
    message_text: str,
    vk_client: AsyncVKApiClient,
    redis_client: Redis,
    ai_client: AIService,
    db_session_factory: async_sessionmaker[AsyncSession],
):
    selected_value = message_text.strip().lower()
    if selected_value != "авто" and selected_value not in IMAGE_ASPECT_RATIOS:
        await send_message(
            user_id,
            "Выберите соотношение сторон кнопкой на клавиатуре.",
            vk_client,
            image_aspect_ratio_keyboard,
        )
        return

    prompt = await get_image_prompt(user_id, redis_client)
    if not prompt:
        await clear_image_generation_context(user_id, redis_client)
        await set_user_state(user_id, UserState.AWAITING_IMAGE_PROMPT, redis_client)
        await send_message(
            user_id,
            "Время ожидания истекло. Пришлите описание изображения ещё раз.",
            vk_client,
            generation_cancel_keyboard,
        )
        return

    reference_images = await get_image_references(user_id, redis_client)
    aspect_ratio = None if selected_value == "авто" else selected_value
    await clear_image_generation_context(user_id, redis_client)
    await set_user_state(user_id, UserState.IDLE, redis_client)
    await _run_generation(
        user_id,
        prompt,
        GenerationType.IMAGE,
        vk_client,
        redis_client,
        ai_client,
        db_session_factory,
        reference_images=reference_images,
        aspect_ratio=aspect_ratio,
    )
