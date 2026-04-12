from datetime import datetime
from typing import Any

import structlog
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, UserProfile
from src.domain.enums import ActivityType
from src.infrastructure.database.repositories import ProfileRepository


async def save_profile_on_confirm(
    callback: CallbackQuery, button: Any, manager: DialogManager
) -> None:
    """Button on_click handler for the confirm window. Saves UserProfile and closes dialog."""
    structlog.contextvars.clear_contextvars()
    container = manager.middleware_data["dishka_container"]
    profile_repo: ProfileRepository = await container.get(ProfileRepository)

    data = manager.dialog_data
    user = callback.from_user

    profile = UserProfile(
        telegram_id=user.id,
        username=user.username,
        level=data.get("level", "B1"),
        goal=data.get("goal", "general"),
        native_lang=data.get("native_lang", "en"),
        target_lang=data.get("target_lang", "de"),
        reminder_enabled=data.get("reminder_enabled", False),
        reminder_time=data.get("reminder_time", "11:00"),
        utc_offset=int(data.get("utc_offset", 1)),
        vocab_card_count=int(data.get("vocab_card_count", DEFAULT_VOCAB_CARD_COUNT)),
        created_at=datetime.now().isoformat(),
        learning_strategy=[
            ActivityType(a)
            for a in data.get("strategy", ["reading", "writing", "listening", "vocab"])
        ],
    )
    await profile_repo.save(profile)
    await manager.done()
