import json
import re
from datetime import datetime, timedelta
from math import ceil
from typing import List, Tuple

from app.core.clients.vk_api import client

from .models import APIResponse, GroupInfo, Parameter, ResultOfCheck
from .utils import format_time

messages = json.load(open("app/modules/analyzer/messages.json", "r", encoding="utf-8"))


def generate_response(group_info: GroupInfo) -> APIResponse:
    good: List[Parameter] = []
    normal: List[Parameter] = []
    bad: List[Parameter] = []
    score = 0

    for field, value in group_info.result_of_check.__dict__.items():
        if field == "average_time_between_posts":
            if value.get("error_message"):
                bad.append(
                    Parameter(
                        id=field,
                        title=messages["average_time_between_posts"]["title"],
                        description=value["error_message"],
                    )
                )
            else:
                avegarage_time_between_posts_in_hours = (
                    value["days"] * 24 + value["hours"] + value["minutes"] / 60
                )
                if avegarage_time_between_posts_in_hours < 6:
                    normal.append(
                        Parameter(
                            id=field,
                            title=messages["average_time_between_posts"]["title"],
                            description=(
                                format_time(
                                    int(value["days"]), int(value["hours"]), int(value["minutes"])
                                )
                                + messages["average_time_between_posts"]["low"]
                            ),
                        )
                    )
                    score += 4.17
                elif 6 < avegarage_time_between_posts_in_hours < 30:
                    good.append(
                        Parameter(
                            id=field,
                            title=messages["average_time_between_posts"]["title"],
                            description=(
                                format_time(
                                    int(value["days"]), int(value["hours"]), int(value["minutes"])
                                )
                                + messages["average_time_between_posts"]["medium"]
                            ),
                        )
                    )
                    score += 8.34
                else:
                    normal.append(
                        Parameter(
                            id=field,
                            title=messages["average_time_between_posts"]["title"],
                            description=(
                                format_time(
                                    int(value["days"]), int(value["hours"]), int(value["minutes"])
                                )
                                + messages["average_time_between_posts"]["high"]
                            ),
                        )
                    )
                    score += 0
        elif field == "er":
            if value > 3:
                good.append(
                    Parameter(
                        id=field,
                        title=messages[field]["title"],
                        description=messages[field]["info"].format(value),
                    )
                )
                score += 8.34
            elif 1 < value < 3:
                normal.append(
                    Parameter(
                        id=field,
                        title=messages[field]["title"],
                        description=messages[field]["info"].format(value),
                    )
                )
                score += 4.17
            else:
                bad.append(
                    Parameter(
                        id=field,
                        title=messages[field]["title"],
                        description=messages[field]["info"].format(value),
                    )
                )
                score += 0
        elif value:
            good.append(
                Parameter(
                    id=field,
                    title=messages[field]["title"],
                    description=messages[field]["positive"],
                )
            )
            score += 8.34
        else:
            if field in ["cover", "description", "can_message"]:
                bad.append(
                    Parameter(
                        id=field,
                        title=messages[field]["title"],
                        description=messages[field]["negative"],
                    )
                )
            else:
                normal.append(
                    Parameter(
                        id=field,
                        title=messages[field]["title"],
                        description=messages[field]["negative"],
                    )
                )

    return APIResponse(
        name=group_info.name,
        photo_100=group_info.photo_100,
        photo_200=group_info.photo_200,
        activity=group_info.activity,
        members_count=group_info.members_count,
        score=ceil(score),
        good=good,
        normal=normal,
        bad=bad,
    )


def get_group_info(group_id: int | str) -> GroupInfo | None:
    group_info, group_id = get_main_info(group_id) # type: ignore
    if group_info:
        posts_info = get_posts_info(group_id, group_info.members_count)
        if posts_info is None:
            return None
        group_info.result_of_check.reposts = posts_info["reposts"]
        group_info.result_of_check.reposts = posts_info["hashtags"]
        group_info.result_of_check.average_time_between_posts = posts_info[
            "average_time_between_posts"
        ]
        group_info.result_of_check.er = posts_info["er"]
        return group_info
    return None


def get_main_info(
    group_id: int | str,
) -> Tuple[GroupInfo, int] | Tuple[None, None] | dict | Tuple[GroupInfo, None]:
    params = {
        "group_id": group_id,
        "fields": "contacts,counters,cover,description,fixed_post,market,activity,members_count",
    }
    response = client.get("groups.getById", params)
    data = response["response"]["groups"][0] if response.get("response") else {}

    if bool(data.get("name")):
        if data.get("is_closed"):
            return None, None
        online_response = client.get("groups.getOnlineStatus", params={"group_id": data.get("id")})
        status = online_response.get("response", {}).get("status") == "online"

        return GroupInfo(
            name=data.get("name"),
            photo_100=data.get("photo_100"),
            photo_200=data.get("photo_200"),
            activity=data.get("activity"),
            members_count=data.get("members_count"),
            result_of_check=ResultOfCheck(
                contacts=bool(data.get("contacts")),
                cover=bool(data.get("cover", {}).get("enabled")),
                # clips=(data["counters"].get("clips", 0) > 0),
                clips=False,
                screen_name=bool(is_default_screen_name(data.get("screen_name"))),
                description=bool(data.get("description")),
                fixed_post=bool(data.get("fixed_post")),
                market=bool(data.get("market", {}).get("enabled")),
                status=status,
                reposts=None,
                hashtags=None,
                average_time_between_posts=None,
                er=None,
            ),
        ), data.get("id")
    return None, None


def get_posts_info(group_id: int, members_count: int):
    params = {"owner_id": f"-{group_id}", "count": 100}
    response = client.get("wall.get", params)
    if response.get("error"):
        return None
    posts = response["response"]["items"]
    recent_posts = filter_recent_posts(posts, 30)

    reposts_exists = bool(sum(1 for post in recent_posts if "copy_history" in post))
    hashtags_exists = bool(
        sum(1 for post in recent_posts if re.search(r"#\w+", post.get("text", "")))
    )
    average_time_between_posts = get_average_time_between_posts(recent_posts)
    er = round(
        sum(
            post["comments"]["count"] + post["likes"]["count"] + post["reposts"]["count"]
            for post in recent_posts
        )
        / members_count
        * 100,
        2,
    )

    return {
        "reposts": reposts_exists,
        "hashtags": hashtags_exists,
        "average_time_between_posts": average_time_between_posts,
        "er": er,
    }


def filter_recent_posts(posts, days: int):
    cutoff_date = datetime.now() - timedelta(days=days)
    return [post for post in posts if datetime.fromtimestamp(post["date"]) > cutoff_date]


def is_default_screen_name(screen_name):
    """
    Проверяет, является ли screen_name дефолтным (формат clubXXXX, publicXXXX и т.д.)
    :param screen_name: Имя группы
    :return: False, если screen_name дефолтный, иначе True
    """
    # Регулярное выражение для дефолтных screen_name (clubXXXX, publicXXXX и т.п.)
    default_pattern = r"^(club|public|event)\d+$"
    return not re.match(default_pattern, screen_name)


def get_average_time_between_posts(posts) -> dict:
    if len(posts) < 2:
        return {"error_message": "За месяц менее 2х постов"}
    timestamps = sorted([post["date"] for post in posts], reverse=True)
    intervals = [timestamps[i] - timestamps[i + 1] for i in range(len(timestamps) - 1)]
    average_interval = sum(intervals) / len(intervals)
    return {
        "days": average_interval // 86400,
        "hours": (average_interval % 86400) // 3600,
        "minutes": (average_interval % 3600) // 60,
    }
