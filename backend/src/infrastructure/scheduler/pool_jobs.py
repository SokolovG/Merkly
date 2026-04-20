"""Nightly pool refill jobs — backend only.

send_reminders and send_scheduled_vocab are NOT here.
Those require Telegram bot.send_message() and belong in frontend/telegram/.
"""

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.src.application.agent.core import LessonAgent
from backend.src.application.article_refill_service import ArticleRefillService
from backend.src.application.listening_refill_service import ListeningRefillService
from backend.src.application.listening_service import ListeningAgent
from backend.src.application.vocab_refill_service import VocabRefillService
from backend.src.domain.enums import ActivityType
from backend.src.infrastructure.database.repositories import ProfileRepository
from backend.src.infrastructure.database.repositories.article_pool_repo import ArticlePoolRepository
from backend.src.infrastructure.database.repositories.listening_pool_repo import (
    ListeningPoolRepository,
)
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository

logger = structlog.get_logger(__name__)


async def refill_all_pools(
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> None:
    """Nightly job: top up vocab pools for all users with VOCAB in learning strategy."""
    async with session_factory() as session:
        profiles = await ProfileRepository(session).all()
    processed = 0
    for profile in profiles:
        if ActivityType.VOCAB not in profile.learning_strategy:
            continue
        try:
            async with session_factory() as session:
                pool_repo = VocabPoolRepository(session)
                refill_service = VocabRefillService(agent=agent, repo=pool_repo)
                await refill_service.refill_if_needed(profile)
            processed += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="refill_all_pools", error=str(exc))
    if processed > 0:
        logger.info("scheduler_job_end", job="refill_all_pools", users_processed=processed)


async def refill_all_article_pools(
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> None:
    """Nightly job: top up article pools for all users with READING in learning_strategy."""
    async with session_factory() as session:
        profiles = await ProfileRepository(session).all()
    processed = 0
    for profile in profiles:
        if ActivityType.READING not in profile.learning_strategy:
            continue
        try:
            async with session_factory() as session:
                repo = ArticlePoolRepository(session)
                refill = ArticleRefillService(agent=agent, repo=repo)
                await refill.refill_if_needed(profile)
            processed += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="refill_all_article_pools", error=str(exc))
    if processed > 0:
        logger.info("scheduler_job_end", job="refill_all_article_pools", users_processed=processed)


async def refill_all_listening_pools(
    session_factory: async_sessionmaker,
    listening_service: ListeningAgent,
) -> None:
    """Nightly job: top up listening pools for all users with LISTENING in learning_strategy."""
    async with session_factory() as session:
        profiles = await ProfileRepository(session).all()
    processed = 0
    for profile in profiles:
        if ActivityType.LISTENING not in profile.learning_strategy:
            continue
        try:
            async with session_factory() as session:
                repo = ListeningPoolRepository(session)
                refill = ListeningRefillService(service=listening_service, repo=repo)
                await refill.refill_if_needed(profile)
            processed += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="refill_all_listening_pools", error=str(exc))
    if processed > 0:
        logger.info(
            "scheduler_job_end", job="refill_all_listening_pools", users_processed=processed
        )
