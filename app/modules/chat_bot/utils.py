import re
from math import ceil

import redis

from app.core.clients.vk_api import client
from app.modules.analyzer.models import APIResponse

redis_client = redis.Redis(host="redis", port=6379, db=0)
redis_client.flushdb()


def extract_group_id(link):
    match = re.search(r"(?:m\.)?(?:vk\.(?:com|ru))/(.*)", link)
    if match:
        return match.group(1)
    return None


def send_message(user_id: int, message: str, keyboard: str | None = None):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": 0,
    }
    if keyboard:
        params["keyboard"] = keyboard
    client.post("messages.send", params)


def set_user_state(user_id, state):
    redis_client.set(f"user_state:{user_id}", state)


def get_user_state(user_id):
    state = redis_client.get(f"user_state:{user_id}")
    return state.decode("utf-8") if state else "idle"


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
