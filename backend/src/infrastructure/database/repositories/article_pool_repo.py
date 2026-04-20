import uuid

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.entities import PooledArticle
from backend.src.domain.ports.article_pool_repo import IArticlePoolRepository
from backend.src.infrastructure.database.models.article_pool_model import ArticlePoolModel

logger = structlog.get_logger(__name__)


class ArticlePoolRepository(IArticlePoolRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def pool_count(self, user_id: uuid.UUID, target_lang: str) -> int:
        result = await self._db.execute(
            select(func.count()).where(
                ArticlePoolModel.user_id == user_id,
                ArticlePoolModel.target_lang == target_lang,
            )
        )
        return result.scalar_one()

    async def get_oldest(self, user_id: uuid.UUID, target_lang: str) -> PooledArticle | None:
        result = await self._db.execute(
            select(ArticlePoolModel)
            .where(
                ArticlePoolModel.user_id == user_id,
                ArticlePoolModel.target_lang == target_lang,
            )
            .order_by(ArticlePoolModel.created_at.asc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PooledArticle(
            id=row.id,
            url=row.url,
            title=row.title,
            text=row.text,
            questions=list(row.questions),
            target_lang=row.target_lang,
        )

    async def mark_served(self, article_id: uuid.UUID) -> None:
        await self._db.execute(delete(ArticlePoolModel).where(ArticlePoolModel.id == article_id))
        await self._db.commit()

    async def add_to_pool(self, user_id: uuid.UUID, articles: list[PooledArticle]) -> None:
        # Fetch existing URLs for dedup
        result = await self._db.execute(
            select(ArticlePoolModel.url).where(
                ArticlePoolModel.user_id == user_id,
                ArticlePoolModel.url.in_([a.url for a in articles]),
            )
        )
        existing_urls = {row for row in result.scalars().all()}

        new_rows = [
            ArticlePoolModel(
                user_id=user_id,
                target_lang=article.target_lang,
                url=article.url,
                title=article.title,
                text=article.text,
                questions=article.questions,
            )
            for article in articles
            if article.url not in existing_urls
        ]
        if new_rows:
            self._db.add_all(new_rows)
            await self._db.commit()
        logger.info(
            "article_pool_add",
            user_id=str(user_id),
            attempted=len(articles),
            added=len(new_rows),
        )
