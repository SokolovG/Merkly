from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Inter-service auth
    BACKEND_API_KEY: SecretStr = SecretStr("dev-secret")

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # Storage
    STORAGE_PROVIDER: Literal["redis", "memory"] = "redis"

    # LLM
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "gpt-4o-mini"

    # Card backend
    CARD_BACKEND: Literal["anki", "mochi"] = "anki"
    ANKI_CONNECT_URL: str = "http://localhost:8765"
    ANKI_DECK: str = "Language::Daily"
    MOCHI_API_KEY: SecretStr = SecretStr("")
    MOCHI_DECK_ID: str = ""
    MOCHI_BASE_URL: str = "https://app.mochi.cards/api"

    # Podcast / Listening
    PODCAST_INDEX_API_KEY: str = ""
    PODCAST_INDEX_API_SECRET: str = ""
    WHISPER_BASE_URL: str = "http://whisper:8000"

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "merkly"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DEBUG: bool = False

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
