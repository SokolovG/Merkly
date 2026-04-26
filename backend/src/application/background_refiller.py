import asyncio
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.src.application.agent.core import LessonAgent
from backend.src.application.article_refill_service import ArticleRefillService
from backend.src.application.listening_refill_service import ListeningRefillService
from backend.src.application.listening_service import ListeningAgent
from backend.src.application.vocab_refill_service import VocabRefillService
from backend.src.domain.constants import WRITING_THEME_FILL_SIZE, WRITING_THEME_POOL_THRESHOLD
from backend.src.domain.entities import UserProfile, WritingTheme
from backend.src.infrastructure.database.repositories.article_pool_repo import ArticlePoolRepository
from backend.src.infrastructure.database.repositories.listening_pool_repo import (
    ListeningPoolRepository,
)
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from backend.src.infrastructure.database.repositories.writing_theme_repo import (
    WritingThemeRepository,
)

logger = structlog.get_logger(__name__)


class BackgroundRefiller:
    """APP-scoped service that owns background pool refill tasks.

    Holds session_maker and agents; creates a fresh DB session per background
    operation so background tasks never share the request session.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        agent: LessonAgent,
        listening_agent: ListeningAgent,
    ) -> None:
        self._session_maker = session_maker
        self._agent = agent
        self._listening_agent = listening_agent

    def schedule_article_refill(self, profile: UserProfile) -> None:
        asyncio.create_task(
            self._article_refill(profile),
            name=f"article_refill_{profile.id}",
        )

    def schedule_listening_refill(self, profile: UserProfile) -> None:
        asyncio.create_task(
            self._listening_refill(profile),
            name=f"listening_refill_{profile.id}",
        )

    def schedule_vocab_refill(self, profile: UserProfile) -> None:
        asyncio.create_task(
            self._vocab_refill(profile),
            name=f"vocab_refill_{profile.id}",
        )

    def schedule_writing_theme_refill(self, profile: UserProfile) -> None:
        asyncio.create_task(
            self._writing_theme_refill(profile),
            name=f"writing_theme_refill_{profile.id}",
        )

    async def _article_refill(self, profile: UserProfile) -> None:
        try:
            async with self._session_maker() as session:
                repo = ArticlePoolRepository(session)
                await ArticleRefillService(agent=self._agent, repo=repo).refill_if_needed(profile)
        except Exception as exc:
            logger.warning("bg_article_refill_error", user_id=str(profile.id), error=str(exc))

    async def _listening_refill(self, profile: UserProfile) -> None:
        try:
            async with self._session_maker() as session:
                repo = ListeningPoolRepository(session)
                await ListeningRefillService(
                    service=self._listening_agent, repo=repo
                ).refill_if_needed(profile)
        except Exception as exc:
            logger.warning("bg_listening_refill_error", user_id=str(profile.id), error=str(exc))

    async def _vocab_refill(self, profile: UserProfile) -> None:
        try:
            async with self._session_maker() as session:
                repo = VocabPoolRepository(session)
                await VocabRefillService(agent=self._agent, repo=repo).refill_if_needed(profile)
        except Exception as exc:
            logger.warning("bg_vocab_refill_error", user_id=str(profile.id), error=str(exc))

    async def _writing_theme_refill(self, profile: UserProfile) -> None:
        """Replicate WritingUseCase._refill_if_needed with a fresh DB session."""
        try:
            async with self._session_maker() as session:
                theme_repo = WritingThemeRepository(session)
                unseen = await theme_repo.count_unseen(
                    user_id=profile.id,
                    target_lang=str(profile.target_lang),
                    level=profile.level,
                )
                if unseen >= WRITING_THEME_POOL_THRESHOLD:
                    return
                logger.info(
                    "bg_writing_theme_pool_refill",
                    user_id=str(profile.id),
                    unseen=unseen,
                    threshold=WRITING_THEME_POOL_THRESHOLD,
                )
                raw = await self._agent.generate_writing_themes(
                    target_lang=str(profile.target_lang),
                    native_lang=str(profile.native_lang),
                    level=profile.level,
                    count=WRITING_THEME_FILL_SIZE,
                )
                themes = [
                    WritingTheme(
                        id=uuid.uuid4(),
                        theme=t,
                        target_lang=str(profile.target_lang),
                        level=profile.level,
                    )
                    for t in raw
                    if t.strip()
                ]
                if themes:
                    await theme_repo.seed(themes)
        except Exception as exc:
            logger.warning("bg_writing_theme_refill_error", user_id=str(profile.id), error=str(exc))
