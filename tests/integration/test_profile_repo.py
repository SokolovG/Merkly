"""Integration tests for ProfileRepository — requires real Postgres."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import UserProfile
from src.domain.enums import Goal, Language
from src.infrastructure.database.repositories.profile_repo import ProfileRepository

pytestmark = pytest.mark.integration


def _make_profile(messenger_id: int, reminder_enabled: bool = False) -> UserProfile:
    return UserProfile(
        messenger_id=messenger_id,
        username="testuser",
        level="B1",
        goal=Goal.TRAVEL,
        native_lang=Language.EN,
        target_lang=Language.DE,
        reminder_enabled=reminder_enabled,
    )


async def test_save_and_get(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=12345)
    await repo.save(profile)

    result = await repo.get(12345)
    assert result is not None
    assert result.messenger_id == 12345
    assert result.level == "B1"
    assert result.goal == Goal.TRAVEL
    assert result.native_lang == Language.EN
    assert result.target_lang == Language.DE


async def test_get_nonexistent_returns_none(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    result = await repo.get(99999)
    assert result is None


async def test_save_is_upsert(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=22345)
    await repo.save(profile)

    profile.level = "B2"
    await repo.save(profile)

    result = await repo.get(22345)
    assert result is not None
    assert result.level == "B2"


async def test_all_with_reminders_filter(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    await repo.save(_make_profile(messenger_id=32345, reminder_enabled=True))
    await repo.save(_make_profile(messenger_id=32346, reminder_enabled=False))

    results = await repo.all_with_reminders()
    assert len(results) == 1
    assert results[0].messenger_id == 32345


async def test_all(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    await repo.save(_make_profile(messenger_id=42345))
    await repo.save(_make_profile(messenger_id=42346))

    results = await repo.all()
    assert len(results) >= 2
