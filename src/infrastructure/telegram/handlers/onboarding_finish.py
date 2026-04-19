from datetime import datetime
from typing import Any

import structlog
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, Identity, UserProfile
from src.domain.enums import ActivityType, Platform
from src.domain.utils import compute_next_reminder_at
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.database.repositories.identity_repo import IdentityRepository


async def save_profile_on_confirm(
    callback: CallbackQuery, button: Any, manager: DialogManager
) -> None:
    """Button on_click handler for the confirm window. Saves UserProfile and closes dialog."""
    structlog.contextvars.clear_contextvars()
    container = manager.middleware_data["dishka_container"]
    session: AsyncSession = await container.get(AsyncSession)
    profile_repo = ProfileRepository(session)
    identity_repo = IdentityRepository(session)

    data = manager.dialog_data
    user = callback.from_user

    profile = UserProfile(
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
    if profile.reminder_enabled:
        fields = {f: getattr(profile, f) for f in profile.__struct_fields__}
        fields["next_reminder_at"] = compute_next_reminder_at(
            profile.reminder_time, profile.utc_offset
        )
        profile = UserProfile(**fields)
    await profile_repo.save(profile)
    identity = Identity(
        user_id=profile.id,
        platform=Platform.TELEGRAM,
        platform_user_id=str(user.id),
    )
    await identity_repo.save(identity)
    await manager.done()
