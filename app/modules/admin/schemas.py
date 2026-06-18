from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class APIModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class AdminLoginRequest(BaseModel):
    login: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str


class GenerationSettingsUpdateRequest(APIModel):
    base_tokens: int = Field(ge=0)
    donut_tokens: int = Field(ge=0)
    post_cost: int = Field(ge=0)
    image_cost: int = Field(ge=0)


class GenerationSettingsResponse(GenerationSettingsUpdateRequest):
    pass


class UsersListItem(APIModel):
    id: int
    avatar: str
    full_name: str
    registered_at: datetime
    is_donut: bool
    balance: int


class UsersListMeta(APIModel):
    limit: int
    offset: int
    has_more: bool


class UsersListResponse(APIModel):
    items: List[UsersListItem]
    meta: UsersListMeta


class LogsListItem(APIModel):
    id: int
    action: Literal["increase", "decrease", "set"]
    amount: int = Field(ge=0)
    change: str
    comment: str | None = None
    datetime: datetime


class GenerationHistoryItem(APIModel):
    id: str
    prompt: str
    datetime: datetime
    type: Literal["post", "image"]
    status: Literal["processing", "success", "failed"]
    cost_rub: float | None = Field(default=None, ge=0)
    result: str | None = None
    error: str | None = None


class UserDetailsResponse(UsersListItem):
    last_balance_reset_at: datetime
    logs: List[LogsListItem]
    generation_history: List[GenerationHistoryItem]


class UserBalanceUpdateRequest(APIModel):
    action: Literal["increase", "decrease", "set"]
    amount: int = Field(ge=0)
    comment: str | None = None


class UserBalanceUpdateResponse(APIModel):
    balance: int
