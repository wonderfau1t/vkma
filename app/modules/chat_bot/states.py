from enum import Enum


class UserState(str, Enum):
    """Состояния диалога пользователя с чат-ботом."""

    INACTIVE = "inactive"
    IDLE = "idle"
    AWAITING_LINK = "awaiting_link"
    AWAITING_POST_PROMPT = "awaiting_post_prompt"
    AWAITING_IMAGE_PROMPT = "awaiting_image_prompt"
    AWAITING_IMAGE_ASPECT_RATIO = "awaiting_image_aspect_ratio"
