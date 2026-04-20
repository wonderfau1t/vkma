from dataclasses import dataclass
from typing import List


@dataclass
class ResultOfCheck:
    contacts: bool
    cover: bool
    clips: bool
    screen_name: bool
    description: bool
    fixed_post: bool
    market: bool
    status: bool
    reposts: bool | None
    hashtags: bool | None
    average_time_between_posts: dict | None
    er: float | None


@dataclass
class GroupInfo:
    name: str | None
    photo_100: str | None
    photo_200: str | None
    activity: str | None
    members_count: int
    result_of_check: ResultOfCheck


@dataclass
class Parameter:
    id: str
    title: str
    description: str


@dataclass
class APIResponse:
    name: str | None
    photo_100: str | None
    photo_200: str | None
    activity: str | None
    members_count: int | None
    score: int
    good: List[Parameter]
    normal: List[Parameter]
    bad: List[Parameter]
