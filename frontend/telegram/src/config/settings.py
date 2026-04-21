from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root .env regardless of working directory
_REPO_ROOT = Path(__file__).resolve().parents[4]  # src/config/settings.py → 4 levels up


class TgSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TELEGRAM_TOKEN: str
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_API_KEY: str = "changeme"
    DEBUG: bool = False
