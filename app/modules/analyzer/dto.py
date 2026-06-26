from dataclasses import dataclass


@dataclass
class VKGroupData:
    id: int
    name: str
    photo_100: str | None
    photo_200: str | None
    activity: str
    members_count: int


@dataclass
class AverageTimeBetweenPosts:
    days: int
    hours: int
    minutes: int


@dataclass
class AnalysisMetrics:
    contacts: bool
    cover: bool
    screen_name: bool
    description: bool
    fixed_post: bool
    market: bool
    reposts: bool
    hashtags: bool
    average_time_between_posts: AverageTimeBetweenPosts
    er: float


@dataclass
class GroupAnalysis:
    group: VKGroupData
    metrics: AnalysisMetrics
