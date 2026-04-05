from pathlib import Path
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
    telegram_token: SecretStr

    # LLM — any OpenAI-compatible endpoint
    # Examples:
    #   OpenAI:   https://api.openai.com/v1
    #   Groq:     https://api.groq.com/openai/v1
    #   Together: https://api.together.xyz/v1
    #   Ollama:   http://localhost:11434/v1  (api_key=ollama)
    #   Mistral:  https://api.mistral.ai/v1
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"

    # Card backend
    card_backend: Literal["anki", "mochi"] = "anki"
    anki_connect_url: str = "http://localhost:8765"
    anki_deck: str = "Language::Daily"
    mochi_api_key: SecretStr = SecretStr("")
    mochi_deck_id: str = ""

    # Storage
    data_dir: Path = Path("./data")
    database_url: str = ""  # e.g. postgresql+asyncpg://user:pass@localhost/merkly
