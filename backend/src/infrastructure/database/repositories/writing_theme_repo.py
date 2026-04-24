import uuid

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.constants import WRITING_THEME_CHOOSE_COUNT
from backend.src.domain.entities import WritingTheme
from backend.src.domain.ports.writing_theme_repo import IWritingThemeRepository
from backend.src.infrastructure.database.models.writing_theme_history_model import (
    WritingThemeHistoryModel,
)
from backend.src.infrastructure.database.models.writing_theme_pool_model import (
    WritingThemePoolModel,
)

logger = structlog.get_logger(__name__)


class WritingThemeRepository(IWritingThemeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def get_unseen(
        self,
        user_id: uuid.UUID,
        target_lang: str,
        level: str | None,
        limit: int = WRITING_THEME_CHOOSE_COUNT,
    ) -> list[WritingTheme]:
        seen_ids_subq = select(WritingThemeHistoryModel.theme_id).where(
            WritingThemeHistoryModel.user_id == user_id
        )

        level_filter = (
            (WritingThemePoolModel.level == level) | (WritingThemePoolModel.level.is_(None))
            if level
            else WritingThemePoolModel.level.is_(None)
        )

        unseen_q = (
            select(WritingThemePoolModel)
            .where(
                WritingThemePoolModel.target_lang == target_lang,
                level_filter,
                WritingThemePoolModel.id.not_in(seen_ids_subq),
            )
            .order_by(func.random())
            .limit(limit)
        )

        result = await self._db.execute(unseen_q)
        rows = result.scalars().all()

        # If the pool is exhausted for this user, reset history and serve fresh
        if not rows:
            logger.info("writing_theme_pool_reset", user_id=str(user_id), target_lang=target_lang)
            await self._db.execute(
                delete(WritingThemeHistoryModel).where(WritingThemeHistoryModel.user_id == user_id)
            )
            await self._db.commit()

            result = await self._db.execute(
                select(WritingThemePoolModel)
                .where(
                    WritingThemePoolModel.target_lang == target_lang,
                    level_filter,
                )
                .order_by(func.random())
                .limit(limit)
            )
            rows = result.scalars().all()

        return [
            WritingTheme(id=row.id, theme=row.theme, target_lang=row.target_lang, level=row.level)
            for row in rows
        ]

    async def get_by_id(self, theme_id: uuid.UUID) -> WritingTheme | None:
        result = await self._db.execute(
            select(WritingThemePoolModel).where(WritingThemePoolModel.id == theme_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return WritingTheme(
            id=row.id, theme=row.theme, target_lang=row.target_lang, level=row.level
        )

    async def count_unseen(self, user_id: uuid.UUID, target_lang: str, level: str | None) -> int:
        seen_ids_subq = select(WritingThemeHistoryModel.theme_id).where(
            WritingThemeHistoryModel.user_id == user_id
        )
        level_filter = (
            (WritingThemePoolModel.level == level) | (WritingThemePoolModel.level.is_(None))
            if level
            else WritingThemePoolModel.level.is_(None)
        )
        result = await self._db.execute(
            select(func.count())
            .select_from(WritingThemePoolModel)
            .where(
                WritingThemePoolModel.target_lang == target_lang,
                level_filter,
                WritingThemePoolModel.id.not_in(seen_ids_subq),
            )
        )
        return result.scalar_one()

    async def mark_seen(self, user_id: uuid.UUID, theme_id: uuid.UUID) -> None:
        stmt = (
            insert(WritingThemeHistoryModel)
            .values(user_id=user_id, theme_id=theme_id)
            .on_conflict_do_nothing(constraint="uq_writing_theme_history_user_theme")
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def seed(self, themes: list[WritingTheme]) -> None:
        """Idempotent insert — skips themes already in the pool (matched by theme text + lang)."""
        if not themes:
            return

        existing_q = select(WritingThemePoolModel.theme).where(
            WritingThemePoolModel.target_lang == themes[0].target_lang
        )
        result = await self._db.execute(existing_q)
        existing_themes = {row for row in result.scalars().all()}

        new_rows = [
            WritingThemePoolModel(
                id=t.id,
                theme=t.theme,
                target_lang=t.target_lang,
                level=t.level,
            )
            for t in themes
            if t.theme not in existing_themes
        ]

        if new_rows:
            self._db.add_all(new_rows)
            await self._db.commit()

        logger.info(
            "writing_theme_pool_seed",
            attempted=len(themes),
            added=len(new_rows),
            skipped=len(themes) - len(new_rows),
        )
