from datetime import datetime
from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from src.domain.entities import UserProfile
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository


async def save_profile_on_confirm(
    callback: CallbackQuery, button: Any, manager: DialogManager
) -> None:
    """Button on_click handler for the confirm window. Saves UserProfile and closes dialog."""
    container = manager.middleware_data["dishka_container"]
    profile_repo: JsonProfileRepository = await container.get(JsonProfileRepository)

    data = manager.dialog_data
    user = callback.from_user

    profile = UserProfile(
        telegram_id=user.id,
        username=user.username,
        level=data.get("level", "B1"),
        goal=data.get("goal", "general"),
        native_lang=data.get("native_lang", "en"),
        target_lang=data.get("target_lang", "de"),
        session_minutes=int(data.get("session_minutes", 30)),
        reminder_enabled=data.get("reminder_enabled", False),
        reminder_time=data.get("reminder_time", "11:00"),
        utc_offset=int(data.get("utc_offset", 1)),
        vocab_card_count=int(data.get("vocab_card_count", 8)),
        created_at=datetime.now().isoformat(),
    )
    await profile_repo.save(profile)
    await manager.done()
