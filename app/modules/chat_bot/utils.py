import re
from math import ceil
from pathlib import Path

from redis.asyncio import Redis

from app.core.clients import AsyncVKApiClient
from app.core.config import settings
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


def extract_photo_url(attachments: list[dict] | None) -> str | None:
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
                return url

        for field in ("photo_2560", "photo_1280", "photo_807", "photo_604"):
            if url := photo.get(field):
                return url

    return None


async def save_image_reference(
    user_id: int, image: bytes, redis_client: Redis
) -> None:
    await redis_client.setex(f"user_image_reference:{user_id}", 3600, image)


async def get_image_reference(user_id: int, redis_client: Redis) -> bytes | None:
    return await redis_client.get(f"user_image_reference:{user_id}")


async def clear_image_reference(user_id: int, redis_client: Redis) -> None:
    await redis_client.delete(f"user_image_reference:{user_id}")


async def upload_message_photo(
    user_id: int,
    image_path: Path,
    vk_client: AsyncVKApiClient,
) -> str:
    token = settings.vk_group_token.get_secret_value()
    upload_server = await vk_client.get(
        "photos.getMessagesUploadServer",
        {"peer_id": user_id},
        token=token,
    )
    upload_result = await vk_client.upload_file(
        upload_server["response"]["upload_url"],
        "photo",
        image_path.name,
        image_path.read_bytes(),
        "image/png",
    )
    saved = await vk_client.post(
        "photos.saveMessagesPhoto",
        {
            "photo": upload_result["photo"],
            "server": upload_result["server"],
            "hash": upload_result["hash"],
        },
        token=token,
    )
    photo = saved["response"][0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    if access_key := photo.get("access_key"):
        attachment += f"_{access_key}"
    return attachment


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
