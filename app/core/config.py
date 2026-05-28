from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    vk_group_token: SecretStr
    vk_protected_key: SecretStr
    vk_service_token: SecretStr
    vk_group_confirmation_token: SecretStr
    ai_service_api_key: SecretStr
    admin_login: str = "admin"
    admin_password: SecretStr
    vk_app_id: int
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    group_id: int
    default_image_cost: int = Field(default=10, gt=0)
    default_post_cost: int = Field(default=2, gt=0)
    default_base_tokens: int = Field(default=30, ge=0)
    default_donut_tokens: int = Field(default=1000, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # type: ignore
