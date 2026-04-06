from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import UserDeck, UserProfile
from src.domain.enums import ActivityType, Goal, Language
from src.infrastructure.database.models.profile_model import ProfileModel


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: ProfileModel) -> UserProfile:
        decks = [UserDeck(**d) for d in (row.decks or [])]
        return UserProfile(
            telegram_id=row.telegram_id,
            username=row.username,
            level=row.level,
            goal=Goal(row.goal),
            native_lang=Language(row.native_lang),
            session_minutes=row.session_minutes,
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
        )

    def _to_values(self, profile: UserProfile) -> dict:
        return {
            "telegram_id": profile.telegram_id,
            "username": profile.username,
            "level": str(profile.level),
            "goal": str(profile.goal),
            "native_lang": str(profile.native_lang),
            "session_minutes": profile.session_minutes,
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
        }

    async def get(self, telegram_id: int) -> UserProfile | None:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def save(self, profile: UserProfile) -> None:
        values = self._to_values(profile)
        stmt = pg_insert(ProfileModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={k: stmt.excluded[k] for k in values if k != "telegram_id"},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def all(self) -> list[UserProfile]:
        result = await self._session.execute(select(ProfileModel))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def all_with_reminders(self) -> list[UserProfile]:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.reminder_enabled == True)  # noqa: E712
        )
        return [self._to_domain(row) for row in result.scalars().all()]
