import re
from math import ceil

from redis.asyncio import Redis

from app.core.clients import AsyncVKApiClient
from app.modules.analyzer.models import APIResponse

from .states import UserState


def extract_group_id(link):
    match = re.search(r"(?:m\.)?(?:vk\.(?:com|ru))/(.*)", link)
    if match:
        return match.group(1)
    return None


async def send_message(
    user_id: int,
    message: str,
    vk_client: AsyncVKApiClient,
    keyboard: str | None = None,
    attachment: str | None = None,
):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": 0,
    }
    if keyboard:
        params["keyboard"] = keyboard
    if attachment:
        params["attachment"] = attachment
    await vk_client.post("messages.send", params)


MAX_IMAGE_REFERENCES = 3
IMAGE_CONTEXT_TTL = 3600


def extract_photo_urls(attachments: list[dict] | None) -> list[str]:
    urls = []
    for attachment in attachments or []:
        if attachment.get("type") != "photo":
            continue

        photo = attachment.get("photo", {})
        sizes = photo.get("sizes", [])
        if sizes:
            largest = max(
                sizes,
                key=lambda size: size.get("width", 0) * size.get("height", 0),
            )
            if url := largest.get("url"):
                urls.append(url)
                continue

        for field in ("photo_2560", "photo_1280", "photo_807", "photo_604"):
            if url := photo.get(field):
                urls.append(url)
                break

    return urls


def extract_photo_url(attachments: list[dict] | None) -> str | None:
    urls = extract_photo_urls(attachments)
    return urls[0] if urls else None


async def save_image_references(
    user_id: int,
    images: list[bytes],
    redis_client: Redis,
) -> int:
    current_images = await get_image_references(user_id, redis_client)
    all_images = [*current_images, *images]
    if len(all_images) > MAX_IMAGE_REFERENCES:
        raise ValueError(
            f"Можно использовать не более {MAX_IMAGE_REFERENCES} референсных изображений"
        )
    if any(not image for image in all_images):
        raise ValueError("Референсное изображение не должно быть пустым")

    list_key = f"user_image_references:{user_id}"
    legacy_key = f"user_image_reference:{user_id}"
    await redis_client.delete(list_key, legacy_key)
    if all_images:
        await redis_client.rpush(list_key, *all_images)
        await redis_client.expire(list_key, IMAGE_CONTEXT_TTL)
    return len(all_images)


async def get_image_references(user_id: int, redis_client: Redis) -> list[bytes]:
    images = await redis_client.lrange(f"user_image_references:{user_id}", 0, -1)
    if images:
        return list(images)

    legacy_image = await redis_client.get(f"user_image_reference:{user_id}")
    return [legacy_image] if legacy_image else []


async def clear_image_references(user_id: int, redis_client: Redis) -> None:
    await redis_client.delete(
        f"user_image_references:{user_id}",
        f"user_image_reference:{user_id}",
    )


async def save_image_prompt(user_id: int, prompt: str, redis_client: Redis) -> None:
    await redis_client.setex(
        f"user_image_prompt:{user_id}",
        IMAGE_CONTEXT_TTL,
        prompt,
    )


async def get_image_prompt(user_id: int, redis_client: Redis) -> str | None:
    prompt = await redis_client.get(f"user_image_prompt:{user_id}")
    if isinstance(prompt, bytes):
        return prompt.decode("utf-8")
    return prompt


async def clear_image_generation_context(
    user_id: int,
    redis_client: Redis,
) -> None:
    await redis_client.delete(
        f"user_image_references:{user_id}",
        f"user_image_reference:{user_id}",
        f"user_image_prompt:{user_id}",
    )


async def save_image_reference(
    user_id: int, image: bytes, redis_client: Redis
) -> None:
    await save_image_references(user_id, [image], redis_client)


async def get_image_reference(user_id: int, redis_client: Redis) -> bytes | None:
    images = await get_image_references(user_id, redis_client)
    return images[0] if images else None


async def clear_image_reference(user_id: int, redis_client: Redis) -> None:
    await clear_image_references(user_id, redis_client)


async def set_user_state(user_id: int, state: UserState, redis_client: Redis) -> None:
    await redis_client.set(f"user_state:{user_id}", state.value)


async def get_user_state(user_id: int, redis_client: Redis) -> UserState:
    state = await redis_client.get(f"user_state:{user_id}")
    if not state:
        return UserState.INACTIVE

    try:
        return UserState(state.decode("utf-8"))
    except ValueError:
        return UserState.INACTIVE


def generate_message_text(data: APIResponse) -> list:
    messages = []

    messages.append(
        "{} Общий результат: {}%\n\nАудит сообщества завершен. Сообщество было проверено по ключевым "
        "параметрам, которые влияют на привлечение клиентов и подписчиков. "
        "Ниже представлены результаты анализа:\n".format(
            "✅" if data.score > 40 else "⚠️" if 20 < data.score < 40 else "⛔️", ceil(data.score)
        )
    )
    for parameter in data.good:
        messages.append(f"\n🟢 {parameter.title}\n{parameter.description}\n")
    for parameter in data.normal:
        messages.append(f"\n🟡 {parameter.title}\n{parameter.description}\n")
    for parameter in data.bad:
        messages.append(f"\n🔴 {parameter.title}\n{parameter.description}\n")

    messages.append(
        "\n✔️Аудит сообщества закончен. Качество подготовки сообщества и его контент стратегия — "
        "определяют интерес к группе и дальнейшее взаимодействие (от крепкого комьюнити до продаж). "
        "Если у вас остались вопросы и вы хотите разобрать их подробнее,"
        "вы всегда можете написать в чат комьюнити смм и таргета 👉https://vk.cc/cEyBab"
    )
    return messages
