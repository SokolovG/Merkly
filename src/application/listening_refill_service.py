import contextlib
import os
import uuid

import structlog

from src.application.listening_service import ListeningAgent
from src.domain.constants import LISTENING_POOL_FILL_SIZE, LISTENING_POOL_THRESHOLD
from src.domain.entities import PooledListeningLesson, UserProfile
from src.domain.ports.listening_pool_repo import IListeningPoolRepository
from src.domain.ports.session_history_repo import ISessionHistoryRepository

logger = structlog.get_logger(__name__)


class ListeningRefillService:
    def __init__(
        self,
        service: ListeningAgent,
        repo: IListeningPoolRepository,
        history_repo: ISessionHistoryRepository,
    ) -> None:
        self._service = service
        self._repo = repo
        self._history_repo = history_repo

    async def refill_if_needed(self, profile: UserProfile) -> bool:
        """Refill listening pool if below threshold. Returns True if refill was triggered."""
        count = await self._repo.pool_count(profile.id, str(profile.target_lang))
        if count >= LISTENING_POOL_THRESHOLD:
            return False
        await self._refill(profile)
        return True

    async def _refill(self, profile: UserProfile) -> None:
        lessons: list[PooledListeningLesson] = []
        target_lang = str(profile.target_lang)
        level = str(profile.level)

        for _ in range(LISTENING_POOL_FILL_SIZE):
            try:
                lesson = await self._service.prepare_lesson(profile)
                # Clean up downloaded audio (not needed for pooled storage)
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(lesson.audio_path)
            except Exception as exc:
                logger.warning("listening_pool_refill_prepare_failed", error=str(exc))
                break

            # Skip if URL already in this batch or already served to user
            if any(les.episode_url == lesson.episode_url for les in lessons):
                logger.info("listening_pool_refill_skip_duplicate", url=lesson.episode_url)
                continue
            if await self._history_repo.has_seen(profile.id, lesson.episode_url):
                logger.info("listening_pool_refill_skip_seen", url=lesson.episode_url)
                continue

            lessons.append(
                PooledListeningLesson(
                    id=uuid.uuid4(),
                    episode_url=lesson.episode_url,
                    title=lesson.title,
                    transcript=lesson.transcript,
                    questions=lesson.questions,
                    target_lang=target_lang,
                    level=level,
                )
            )

        if lessons:
            await self._repo.add_to_pool(profile.id, lessons)
            logger.info(
                "listening_pool_refill_complete",
                user_id=str(profile.id),
                count=len(lessons),
            )
        else:
            logger.warning("listening_pool_refill_no_lessons", user_id=str(profile.id))
