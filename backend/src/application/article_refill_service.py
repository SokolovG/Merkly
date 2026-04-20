import uuid

import structlog

from backend.src.application.agent.core import LessonAgent
from backend.src.domain.constants import ARTICLE_POOL_FILL_SIZE, ARTICLE_POOL_THRESHOLD
from backend.src.domain.entities import PooledArticle, UserProfile
from backend.src.domain.ports.article_pool_repo import IArticlePoolRepository

logger = structlog.get_logger(__name__)


class ArticleRefillService:
    def __init__(self, agent: LessonAgent, repo: IArticlePoolRepository) -> None:
        self._agent = agent
        self._repo = repo

    async def refill_if_needed(self, profile: UserProfile) -> bool:
        """Refill article pool if below threshold. Returns True if refill was triggered."""
        count = await self._repo.pool_count(profile.id, str(profile.target_lang))
        if count >= ARTICLE_POOL_THRESHOLD:
            return False
        await self._refill(profile)
        return True

    async def _refill(self, profile: UserProfile) -> None:
        level = profile.level
        goal = str(profile.goal)
        native_lang = str(profile.native_lang)
        target_lang = str(profile.target_lang)

        articles: list[PooledArticle] = []
        seen_urls: set[str] = set()

        for _ in range(ARTICLE_POOL_FILL_SIZE):
            try:
                title, url, text, questions = await self._agent.prepare_reading_lesson(
                    level=level,
                    goal=goal,
                    native_lang=native_lang,
                    target_lang=target_lang,
                    recent_topics=[],
                    question_count=profile.question_count,
                )
            except Exception as exc:
                logger.warning("article_refill_prepare_failed", error=str(exc))
                continue

            if url in seen_urls:
                logger.info("article_refill_skip_duplicate", url=url)
                continue

            seen_urls.add(url)
            articles.append(
                PooledArticle(
                    id=uuid.uuid4(),
                    url=url,
                    title=title,
                    text=text,
                    questions=questions,
                    target_lang=target_lang,
                )
            )

        if articles:
            await self._repo.add_to_pool(profile.id, articles)
            logger.info(
                "article_refill_complete",
                user_id=str(profile.id),
                articles_added=len(articles),
            )
        else:
            logger.warning("article_refill_no_articles", user_id=str(profile.id))
