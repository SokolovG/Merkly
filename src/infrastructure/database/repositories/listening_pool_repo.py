import uuid

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import PooledListeningLesson
from src.domain.ports.listening_pool_repo import IListeningPoolRepository
from src.infrastructure.database.models.listening_history_model import ListeningHistoryModel
from src.infrastructure.database.models.listening_pool_model import ListeningPoolModel

logger = structlog.get_logger(__name__)


class ListeningPoolRepository(IListeningPoolRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def pool_count(self, user_id: uuid.UUID, target_lang: str) -> int:
        result = await self._db.execute(
            select(func.count()).where(
                ListeningPoolModel.user_id == user_id,
                ListeningPoolModel.target_lang == target_lang,
            )
        )
        return result.scalar_one()

    async def get_oldest(
        self, user_id: uuid.UUID, target_lang: str
    ) -> PooledListeningLesson | None:
        result = await self._db.execute(
            select(ListeningPoolModel)
            .where(
                ListeningPoolModel.user_id == user_id,
                ListeningPoolModel.target_lang == target_lang,
            )
            .order_by(ListeningPoolModel.created_at.asc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PooledListeningLesson(
            id=row.id,
            episode_url=row.episode_url,
            title=row.title,
            transcript=row.transcript,
            questions=list(row.questions),
            target_lang=row.target_lang,
            level=row.level,
        )

    async def mark_served(self, lesson_id: uuid.UUID) -> None:
        result = await self._db.execute(
            select(
                ListeningPoolModel.user_id,
                ListeningPoolModel.episode_url,
                ListeningPoolModel.target_lang,
            ).where(ListeningPoolModel.id == lesson_id)
        )
        row = result.one_or_none()
        await self._db.execute(delete(ListeningPoolModel).where(ListeningPoolModel.id == lesson_id))
        if row:
            self._db.add(
                ListeningHistoryModel(
                    user_id=row.user_id,
                    episode_url=row.episode_url,
                    target_lang=row.target_lang,
                )
            )
        await self._db.commit()

    async def record_history(self, user_id: uuid.UUID, episode_url: str, target_lang: str) -> None:
        self._db.add(
            ListeningHistoryModel(
                user_id=user_id,
                episode_url=episode_url,
                target_lang=target_lang,
            )
        )
        await self._db.commit()

    async def add_to_pool(self, user_id: uuid.UUID, lessons: list[PooledListeningLesson]) -> None:
        # Dedup against listening_history (episodes already served to this user)
        result = await self._db.execute(
            select(ListeningHistoryModel.episode_url).where(
                ListeningHistoryModel.user_id == user_id,
                ListeningHistoryModel.episode_url.in_([les.episode_url for les in lessons]),
            )
        )
        seen_urls = {row for row in result.scalars().all()}

        new_rows = [
            ListeningPoolModel(
                user_id=user_id,
                target_lang=lesson.target_lang,
                episode_url=lesson.episode_url,
                title=lesson.title,
                transcript=lesson.transcript,
                questions=lesson.questions,
                level=lesson.level,
            )
            for lesson in lessons
            if lesson.episode_url not in seen_urls
        ]
        if new_rows:
            self._db.add_all(new_rows)
            await self._db.commit()
        logger.info(
            "listening_pool_add",
            user_id=str(user_id),
            attempted=len(lessons),
            added=len(new_rows),
        )
