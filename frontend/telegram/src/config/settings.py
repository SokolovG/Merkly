from pydantic_settings import BaseSettings, SettingsConfigDict


class TgSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TELEGRAM_TOKEN: str
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_API_KEY: str = "changeme"
    DEBUG: bool = False
