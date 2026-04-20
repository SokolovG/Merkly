import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.entities import UserDeck, UserProfile
from backend.src.domain.enums import ActivityType, Goal, Language
from backend.src.domain.ports.profile_repo import IProfileRepository
from backend.src.infrastructure.database.models.profile_model import ProfileModel

logger = structlog.get_logger(__name__)


class ProfileRepository(IProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: ProfileModel) -> UserProfile:
        decks = [UserDeck(**d) for d in (row.decks or [])]
        return UserProfile(
            username=row.username,
            level=row.level,
            goal=Goal(row.goal),
            native_lang=Language(row.native_lang),
            target_lang=Language(row.target_lang),
            reminder_enabled=row.reminder_enabled,
            reminder_time=row.reminder_time,
            utc_offset=row.utc_offset,
            vocab_card_count=row.vocab_card_count,
            created_at=row.created_at.isoformat() if row.created_at else "",
            decks=decks,
            active_deck_id=row.active_deck_id,
            vocab_scheduler_enabled=row.vocab_scheduler_enabled,
            vocab_scheduler_time=row.vocab_scheduler_time,
            vocab_scheduler_deck_id=row.vocab_scheduler_deck_id,
            learning_strategy=[
                ActivityType(a)
                for a in (row.learning_strategy or ["reading", "writing", "listening", "vocab"])
            ],
            question_count=row.question_count,
            episode_duration_min=row.episode_duration_min,
            next_reminder_at=row.next_reminder_at,
            id=row.id,
        )

    def _to_values(self, profile: UserProfile) -> dict:
        return {
            "username": profile.username,
            "level": str(profile.level),
            "goal": str(profile.goal),
            "native_lang": str(profile.native_lang),
            "target_lang": str(profile.target_lang),
            "reminder_enabled": profile.reminder_enabled,
            "reminder_time": profile.reminder_time,
            "utc_offset": profile.utc_offset,
            "vocab_card_count": profile.vocab_card_count,
            "decks": [{"name": d.name, "backend_id": d.backend_id} for d in profile.decks],
            "active_deck_id": profile.active_deck_id,
            "vocab_scheduler_enabled": profile.vocab_scheduler_enabled,
            "vocab_scheduler_time": profile.vocab_scheduler_time,
            "vocab_scheduler_deck_id": profile.vocab_scheduler_deck_id,
            "learning_strategy": [str(a) for a in profile.learning_strategy],
            "question_count": profile.question_count,
            "episode_duration_min": profile.episode_duration_min,
            "next_reminder_at": profile.next_reminder_at,
        }

    async def get_by_id(self, user_id: uuid.UUID) -> UserProfile | None:
        result = await self._session.execute(select(ProfileModel).where(ProfileModel.id == user_id))
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def save(self, profile: UserProfile) -> None:
        values = {**self._to_values(profile), "id": profile.id}
        await self._session.merge(ProfileModel(**values))
        await self._session.commit()
        logger.debug("db_save", table="profiles", user_id=str(profile.id))

    async def all(self) -> list[UserProfile]:
        result = await self._session.execute(select(ProfileModel))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def all_with_reminders(self) -> list[UserProfile]:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.reminder_enabled == True)  # noqa: E712
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_due_for_reminder(self) -> list[UserProfile]:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ProfileModel).where(
                ProfileModel.reminder_enabled == True,  # noqa: E712
                ProfileModel.next_reminder_at.is_not(None),
                ProfileModel.next_reminder_at <= now,
            )
        )
        return [self._to_domain(row) for row in result.scalars().all()]
