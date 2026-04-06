from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram
    TELEGRAM_TOKEN: SecretStr

    # LLM — any OpenAI-compatible endpoint
    # Examples:
    #   OpenAI:   https://api.openai.com/v1
    #   Groq:     https://api.groq.com/openai/v1
    #   Together: https://api.together.xyz/v1
    #   Ollama:   http://localhost:11434/v1  (api_key=ollama)
    #   Mistral:  https://api.mistral.ai/v1
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "gpt-4o-mini"

    # Card backend
    CARD_BACKEND: Literal["anki", "mochi"] = "anki"
    anki_connect_url: str = "http://localhost:8765"
    anki_deck: str = "Language::Daily"
    mochi_api_key: SecretStr = SecretStr("")
    mochi_deck_id: str = ""

    # Database
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    @property
    def async_database_url(self) -> str:
        """An asynchronous URL for the app to run."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
