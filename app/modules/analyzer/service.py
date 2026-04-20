import json
import re
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Literal, Tuple

from app.core.clients import AsyncVKApiClient

from .models import APIResponse, GroupInfo, Parameter, ResultOfCheck
from .utils import format_time

MESSAGES = json.load(open("app/modules/analyzer/messages.json", "r", encoding="utf-8"))

GOOD_SCORE = 8.34
NORMAL_SCORE = 4.17


def build_analysis_response(group_info: GroupInfo) -> APIResponse:
    """Основная функция: строит финальный отчёт с оценкой группы."""
    good: List[Parameter] = []
    normal: List[Parameter] = []
    bad: List[Parameter] = []
    total_score: float = 0.0
    for field, value in group_info.result_of_check.__dict__.items():
        category, parameter, score_delta = _evaluate_field(field, value, MESSAGES)
        if category == "good":
            good.append(parameter)
        elif category == "normal":
            normal.append(parameter)
        elif category == "bad":
            bad.append(parameter)
        total_score += score_delta

    return APIResponse(
        name=group_info.name,
        photo_100=group_info.photo_100,
        photo_200=group_info.photo_200,
        activity=group_info.activity,
        members_count=group_info.members_count,
        score=ceil(total_score),
        good=good,
        normal=normal,
        bad=bad,
    )


async def fetch_group_analysis(
    group_id: int | str, vk_client: AsyncVKApiClient
) -> GroupInfo | None:
    """Получение всех данных и возврат GroupInfo"""
    group_info, real_id = await fetch_basic_group_info(group_id, vk_client)
    if group_info is None:
        return None

    posts_data = await analyze_posts(real_id, group_info.members_count, vk_client)
    if posts_data is None:
        return None

    group_info.result_of_check.reposts = posts_data["reposts"]
    group_info.result_of_check.hashtags = posts_data["hashtags"]
    group_info.result_of_check.average_time_between_posts = posts_data["average_time_between_posts"]
    group_info.result_of_check.er = posts_data["er"]

    return group_info


async def fetch_basic_group_info(
    group_id: int | str, vk_client: AsyncVKApiClient
) -> tuple[None, Literal[0]] | tuple[GroupInfo, Any]:
    """Получение основной информации о группе"""
    params = {
        "group_id": group_id,
        "fields": "contacts,counters,cover,description,fixed_post,market,activity,members_count",
    }
    response = await vk_client.get("groups.getById", params)
    data: dict = response.get("response", {}).get("groups", [{}])[0]

    if not data.get("name") or data.get("is_closed"):
        return None, 0

    online_status = await vk_client.get("groups.getOnlineStatus", {"group_id": data["id"]})
    is_online = online_status.get("response", {}).get("status") == "online"

    return GroupInfo(
        name=data.get("name"),
        photo_100=data.get("photo_100"),
        photo_200=data.get("photo_200"),
        activity=data.get("activity"),
        members_count=data.get("members_count", 0),
        result_of_check=ResultOfCheck(
            contacts=bool(data.get("contacts")),
            cover=bool(data.get("cover", {}).get("enabled")),
            # clips=(data["counters"].get("clips", 0) > 0),
            clips=False,
            screen_name=bool(is_custom_screen_name(data.get("screen_name"))),
            description=bool(data.get("description")),
            fixed_post=bool(data.get("fixed_post")),
            market=bool(data.get("market", {}).get("enabled")),
            status=is_online,
            reposts=None,
            hashtags=None,
            average_time_between_posts=None,
            er=None,
        ),
    ), data.get("id", 0)


async def analyze_posts(
    group_id: int, members_count: int, vk_client: AsyncVKApiClient
) -> Dict[str, Any] | None:
    """Получает посты и возвращает все нужные метрики."""
    response = await vk_client.get("wall.get", {"owner_id": f"-{group_id}", "count": 100})

    if response.get("error"):
        return None

    posts = response["response"]["items"]
    recent_posts = get_recent_posts(posts, days=30)
    if not recent_posts:
        return None

    reposts_count = 0
    hashtags_count = 0
    total_engagements = 0

    hashtag_regex = re.compile(r"#\w+")

    for post in recent_posts:
        if "copy_history" in post:
            reposts_count += 1
        if hashtag_regex.search(post.get("text", "")):
            hashtags_count += 1

        total_engagements += (
            post.get("comments", {}).get("count", 0)
            + post.get("likes", {}).get("count", 0)
            + post.get("reposts", {}).get("count", 0)
        )

    er = round((total_engagements / members_count * 100), 2) if members_count > 0 else 0
    return {
        "reposts": reposts_count > 0,
        "hashtags": hashtags_count > 0,
        "average_time_between_posts": calculate_average_time_between_posts(recent_posts),
        "er": er,
    }


def get_recent_posts(posts: list, days: int = 30) -> list:
    """Фильтрует посты, оставляя только за последние N дней."""
    cutoff = datetime.now() - timedelta(days=days)
    return [post for post in posts if datetime.fromtimestamp(post["date"]) > cutoff]


def is_custom_screen_name(screen_name: str | None) -> bool:
    """Возвращает True, если у группы кастомный screen_name (не clubXXXX и т.п.)."""
    if not screen_name or not isinstance(screen_name, str):
        return False
    return not re.match(r"^(club|public|event)\d+$", screen_name)


def calculate_average_time_between_posts(posts: list) -> dict:
    """Считает среднее время между постами."""
    if len(posts) < 2:
        return {"error_message": "За месяц менее 2х постов"}

    timestamps = sorted(post["date"] for post in posts)
    intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    avg_seconds = sum(intervals) / len(intervals)

    return {
        "days": int(avg_seconds // 86400),
        "hours": int((avg_seconds % 86400) // 3600),
        "minutes": int((avg_seconds % 3600) // 60),
    }


def _evaluate_field(field: str, value: Any, messages: dict) -> Tuple[str, Parameter, float]:
    """Оценивает одно поле и возвращает категорию, Parameter и баллы."""
    if field == "average_time_between_posts":
        return _evaluate_average_time(value, messages)
    if field == "er":
        return _evaluate_er(value, messages)

    # Все остальные поля — обычные bool
    if value:
        param = Parameter(
            id=field,
            title=messages[field]["title"],
            description=messages[field]["positive"],
        )
        return "good", param, GOOD_SCORE

    # Плохие поля
    description = messages[field]["negative"]
    if field in {"cover", "description", "can_message"}:
        param = Parameter(id=field, title=messages[field]["title"], description=description)
        return "bad", param, 0.0

    param = Parameter(id=field, title=messages[field]["title"], description=description)
    return "normal", param, 0.0


def _evaluate_average_time(value: dict, messages: dict) -> Tuple[str, Parameter, float]:
    if value.get("error_message"):
        param = Parameter(
            id="average_time_between_posts",
            title=messages["average_time_between_posts"]["title"],
            description=value["error_message"],
        )
        return "bad", param, 0.0

    hours_total = value["days"] * 24 + value["hours"] + value["minutes"] / 60
    time_str = format_time(int(value["days"]), int(value["hours"]), int(value["minutes"]))

    if hours_total < 6:
        param = Parameter(
            id="average_time_between_posts",
            title=messages["average_time_between_posts"]["title"],
            description=time_str + messages["average_time_between_posts"]["low"],
        )
        return "normal", param, NORMAL_SCORE
    elif 6 <= hours_total <= 30:
        param = Parameter(
            id="average_time_between_posts",
            title=messages["average_time_between_posts"]["title"],
            description=time_str + messages["average_time_between_posts"]["medium"],
        )
        return "good", param, GOOD_SCORE

    param = Parameter(
        id="average_time_between_posts",
        title=messages["average_time_between_posts"]["title"],
        description=time_str + messages["average_time_between_posts"]["low"],
    )

    return "normal", param, 0.0


def _evaluate_er(value: float, messages: dict) -> Tuple[str, Parameter, float]:
    """Специальная логика для ER (коэффициента вовлечённости)."""
    param = Parameter(
        id="er",
        title=messages["er"]["title"],
        description=messages["er"]["info"].format(value),
    )

    if value > 3:
        return "good", param, GOOD_SCORE
    if 1 < value < 3:
        return "normal", param, NORMAL_SCORE
    return "bad", param, 0.0
