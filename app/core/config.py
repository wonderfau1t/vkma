from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    vk_group_token: SecretStr
    vk_protected_key: SecretStr
    vk_service_token: SecretStr
    vk_group_confirmation_token: SecretStr
    ai_service_api_key: SecretStr
    vk_app_id: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # type: ignore
