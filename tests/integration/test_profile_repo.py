"""Integration tests for ProfileRepository — requires real Postgres."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import UserProfile
from src.domain.enums import Goal, Language
from src.infrastructure.database.repositories.profile_repo import ProfileRepository

pytestmark = pytest.mark.integration


def _make_profile(reminder_enabled: bool = False) -> UserProfile:
    return UserProfile(
        username="testuser",
        level="B1",
        goal=Goal.TRAVEL,
        native_lang=Language.EN,
        target_lang=Language.DE,
        reminder_enabled=reminder_enabled,
    )


async def test_save_and_get(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    profile = _make_profile()
    await repo.save(profile)

    result = await repo.get_by_id(profile.id)
    assert result is not None
    assert result.id == profile.id
    assert result.level == "B1"
    assert result.goal == Goal.TRAVEL
    assert result.native_lang == Language.EN
    assert result.target_lang == Language.DE


async def test_get_nonexistent_returns_none(db_session: AsyncSession) -> None:
    import uuid

    repo = ProfileRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


async def test_save_is_upsert(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    profile = _make_profile()
    await repo.save(profile)

    fields = {f: getattr(profile, f) for f in profile.__struct_fields__}
    fields["level"] = "B2"
    updated = UserProfile(**fields)
    await repo.save(updated)

    result = await repo.get_by_id(profile.id)
    assert result is not None
    assert result.level == "B2"


async def test_all_with_reminders_filter(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    reminder_profile = _make_profile(reminder_enabled=True)
    await repo.save(reminder_profile)
    await repo.save(_make_profile(reminder_enabled=False))

    results = await repo.all_with_reminders()
    result_ids = {r.id for r in results}
    assert reminder_profile.id in result_ids


async def test_all(db_session: AsyncSession) -> None:
    repo = ProfileRepository(db_session)
    p1 = _make_profile()
    p2 = _make_profile()
    await repo.save(p1)
    await repo.save(p2)

    results = await repo.all()
    assert len(results) >= 2
