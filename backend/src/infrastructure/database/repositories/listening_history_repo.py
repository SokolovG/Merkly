import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.ports.listening_history_repo import IListeningHistoryRepository
from backend.src.infrastructure.database.models.listening_history_model import ListeningHistoryModel


class ListeningHistoryRepository(IListeningHistoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def record(self, user_id: uuid.UUID, episode_url: str, target_lang: str) -> None:
        try:
            self._db.add(
                ListeningHistoryModel(
                    user_id=user_id,
                    episode_url=episode_url,
                    target_lang=target_lang,
                )
            )
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
