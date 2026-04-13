import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import UserDeck, UserProfile
from src.domain.enums import ActivityType, Goal, Language, MessengerType
from src.domain.ports.profile_repo import IProfileRepository
from src.infrastructure.database.models.profile_model import ProfileModel

logger = structlog.get_logger(__name__)


class ProfileRepository(IProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: ProfileModel) -> UserProfile:
        decks = [UserDeck(**d) for d in (row.decks or [])]
        return UserProfile(
            messenger_id=row.messenger_id,
            messenger_type=MessengerType(row.messenger_type),
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
            id=row.id,
        )

    def _to_values(self, profile: UserProfile) -> dict:
        return {
            "messenger_id": profile.messenger_id,
            "messenger_type": str(profile.messenger_type),
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
        }

    async def get(self, messenger_id: int) -> UserProfile | None:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.messenger_id == messenger_id)
        )
        row = result.scalar_one_or_none()
        profile = self._to_domain(row) if row else None
        return profile

    async def save(self, profile: UserProfile) -> None:
        values = {**self._to_values(profile), "id": profile.id}
        stmt = pg_insert(ProfileModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["messenger_id"],
            set_={k: stmt.excluded[k] for k in values if k not in ("messenger_id", "id")},
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.debug("db_save", table="profiles", messenger_id=profile.messenger_id)

    async def all(self) -> list[UserProfile]:
        result = await self._session.execute(select(ProfileModel))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def all_with_reminders(self) -> list[UserProfile]:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.reminder_enabled == True)  # noqa: E712
        )
        return [self._to_domain(row) for row in result.scalars().all()]
