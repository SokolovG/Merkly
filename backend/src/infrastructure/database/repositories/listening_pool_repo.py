import uuid

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.entities import PooledListeningLesson
from backend.src.domain.ports.listening_pool_repo import IListeningPoolRepository
from backend.src.infrastructure.database.models.listening_history_model import ListeningHistoryModel
from backend.src.infrastructure.database.models.listening_pool_model import ListeningPoolModel

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
            try:
                self._db.add(
                    ListeningHistoryModel(
                        user_id=row.user_id,
                        episode_url=row.episode_url,
                        target_lang=row.target_lang,
                    )
                )
                await self._db.commit()
            except IntegrityError:
                await self._db.rollback()
        else:
            await self._db.commit()

    async def add_to_pool(self, user_id: uuid.UUID, lessons: list[PooledListeningLesson]) -> None:
        if not lessons:
            return

        candidate_urls = [les.episode_url for les in lessons]

        # Dedup against listening_history (already served)
        history_result = await self._db.execute(
            select(ListeningHistoryModel.episode_url).where(
                ListeningHistoryModel.user_id == user_id,
                ListeningHistoryModel.episode_url.in_(candidate_urls),
            )
        )
        seen_urls: set[str] = set(history_result.scalars().all())

        # Dedup against current pool (already queued, e.g. from previous refill)
        pool_result = await self._db.execute(
            select(ListeningPoolModel.episode_url).where(
                ListeningPoolModel.user_id == user_id,
                ListeningPoolModel.episode_url.in_(candidate_urls),
            )
        )
        seen_urls |= set(pool_result.scalars().all())

        # In-batch dedup (fetchers are stateless — same episode can appear twice in one batch)
        seen_in_batch: set[str] = set()
        new_rows = []
        for lesson in lessons:
            if lesson.episode_url in seen_urls or lesson.episode_url in seen_in_batch:
                continue
            seen_in_batch.add(lesson.episode_url)
            new_rows.append(
                ListeningPoolModel(
                    user_id=user_id,
                    target_lang=lesson.target_lang,
                    episode_url=lesson.episode_url,
                    title=lesson.title,
                    transcript=lesson.transcript,
                    questions=lesson.questions,
                    level=lesson.level,
                )
            )

        if new_rows:
            self._db.add_all(new_rows)
            await self._db.commit()
        logger.info(
            "listening_pool_add",
            user_id=str(user_id),
            attempted=len(lessons),
            added=len(new_rows),
        )
