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
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DEBUG: bool = False

    # Bug reports
    BUG_REPORT_CHAT_ID: str = ""  # empty = disabled, fall back to GitHub URL
    GITHUB_REPO_URL: str = ""  # e.g. https://github.com/SokolovG/merkly

    @property
    def async_database_url(self) -> str:
        """An asynchronous URL for the app to run."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
