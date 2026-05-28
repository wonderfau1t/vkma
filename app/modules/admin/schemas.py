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
    post_cost: int = Field(gt=0)
    image_cost: int = Field(gt=0)


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


class UserDetailsResponse(UsersListItem):
    last_balance_reset_at: datetime
    logs: List[LogsListItem]


class UserBalanceUpdateRequest(APIModel):
    action: Literal["increase", "decrease", "set"]
    amount: int = Field(ge=0)
    comment: str | None = None


class UserBalanceUpdateResponse(APIModel):
    balance: int
