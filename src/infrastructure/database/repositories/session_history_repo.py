from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import ActivityType
from src.domain.ports.session_history_repo import ISessionHistoryRepository
from src.infrastructure.database.models.profile_model import ProfileModel
from src.infrastructure.database.models.session_history_model import SessionHistoryModel


class SessionHistoryRepository(ISessionHistoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def _resolve_profile_id(self, telegram_id: int) -> int:
        result = await self._db.execute(
            select(ProfileModel.id).where(ProfileModel.telegram_id == telegram_id)
        )
        return result.scalar_one()

    async def has_seen(self, user_id: int, url: str) -> bool:
        profile_id = await self._resolve_profile_id(user_id)
        result = await self._db.execute(
            select(func.count()).where(
                SessionHistoryModel.user_id == profile_id,
                SessionHistoryModel.url == url,
            )
        )
        return result.scalar_one() > 0

    async def record(self, user_id: int, url: str, activity_type: ActivityType) -> None:
        profile_id = await self._resolve_profile_id(user_id)
        self._db.add(
            SessionHistoryModel(
                user_id=profile_id,
                url=url,
                activity_type=str(activity_type),
            )
        )
        await self._db.commit()
