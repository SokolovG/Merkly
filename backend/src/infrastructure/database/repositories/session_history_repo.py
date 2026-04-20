import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.enums import ActivityType
from backend.src.domain.ports.session_history_repo import ISessionHistoryRepository
from backend.src.infrastructure.database.models.session_history_model import SessionHistoryModel


class SessionHistoryRepository(ISessionHistoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def has_seen(self, user_id: uuid.UUID, url: str) -> bool:
        result = await self._db.execute(
            select(func.count()).where(
                SessionHistoryModel.user_id == user_id,
                SessionHistoryModel.url == url,
            )
        )
        return result.scalar_one() > 0

    async def record(self, user_id: uuid.UUID, url: str, activity_type: ActivityType) -> None:
        self._db.add(
            SessionHistoryModel(
                user_id=user_id,
                url=url,
                activity_type=str(activity_type),
            )
        )
        await self._db.commit()
