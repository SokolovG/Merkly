import asyncio
import uuid
from contextlib import suppress
from dataclasses import dataclass

import structlog

from backend.src.application.agent.core import LessonAgent
from backend.src.domain.constants import WRITING_THEME_FILL_SIZE, WRITING_THEME_POOL_THRESHOLD
from backend.src.domain.entities import Identity, UserProfile, WritingTheme
from backend.src.domain.ports.writing_theme_repo import IWritingThemeRepository
from backend.src.infrastructure.exceptions import InternalServerError, NotFoundError
from backend.src.infrastructure.session_store import RedisSessionStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class WritingSessionResult:
    session_id: str
    task: str
    theme: str


class WritingUseCase:
    def __init__(
        self,
        agent: LessonAgent,
        store: RedisSessionStore,
        theme_repo: IWritingThemeRepository,
    ) -> None:
        self._agent = agent
        self._store = store
        self._theme_repo = theme_repo

    async def get_themes(
        self,
        profile: UserProfile,
        limit: int = 1,
    ) -> list[WritingTheme]:
        """Return unseen exam-style themes from the DB pool for this user.

        Default limit=1 for the random-theme flow (/writing command).
        Pass limit=5 for the choose-theme picker flow.
        Resets history automatically when pool is exhausted.
        On pool-miss (table empty), generates themes via LLM and seeds the pool.
        """
        try:
            themes = await self._theme_repo.get_unseen(
                user_id=profile.id,
                target_lang=str(profile.target_lang),
                level=profile.level,
                limit=limit,
            )
            if themes:
                asyncio.create_task(
                    self._refill_if_needed(profile),
                    name=f"writing_theme_refill_{profile.id}",
                )
                return themes

            # Pool empty — generate via LLM synchronously, seed, then return
            new_themes = await self._generate_and_seed(
                profile, count=max(limit, WRITING_THEME_FILL_SIZE)
            )
            return new_themes[:limit]
        except InternalServerError:
            raise
        except Exception as exc:
            raise InternalServerError(
                message="Failed to fetch writing themes",
                details={"user_id": str(profile.id)},
            ) from exc

    async def _refill_if_needed(self, profile: UserProfile) -> None:
        """Background task: seed more themes if unseen count is below threshold."""
        try:
            unseen = await self._theme_repo.count_unseen(
                user_id=profile.id,
                target_lang=str(profile.target_lang),
                level=profile.level,
            )
            if unseen >= WRITING_THEME_POOL_THRESHOLD:
                return
            logger.info(
                "writing_theme_pool_refill",
                user_id=str(profile.id),
                unseen=unseen,
                threshold=WRITING_THEME_POOL_THRESHOLD,
            )
            await self._generate_and_seed(profile, count=WRITING_THEME_FILL_SIZE)
        except Exception as exc:
            logger.warning("writing_theme_refill_error", user_id=str(profile.id), error=str(exc))

    async def _generate_and_seed(self, profile: UserProfile, count: int) -> list[WritingTheme]:
        raw = await self._agent.generate_writing_themes(
            target_lang=str(profile.target_lang),
            native_lang=str(profile.native_lang),
            level=profile.level,
            count=count,
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
            await self._theme_repo.seed(themes)
        return themes

    async def start(
        self,
        profile: UserProfile,
        identity: Identity,
        theme_id: uuid.UUID,
        mode: str = "article",
    ) -> WritingSessionResult:
        """Create a standalone writing session from a theme pool entry.

        Looks up theme text from the DB, generates the writing task,
        then marks the theme as seen in the user's history.
        """

        theme_obj = await self._theme_repo.get_by_id(theme_id)
        if theme_obj is None:
            raise NotFoundError("WritingTheme", theme_id)

        try:
            task = await self._agent.generate_standalone_writing_task(
                theme=theme_obj.theme,
                target_lang=str(profile.target_lang),
                level=profile.level,
                mode=mode,
            )
        except Exception as exc:
            raise InternalServerError(
                message="Failed to generate writing task",
                details={"user_id": str(profile.id), "theme": theme_obj.theme},
            ) from exc

        with suppress(Exception):
            await self._theme_repo.mark_seen(user_id=profile.id, theme_id=theme_id)

        session_id = str(uuid.uuid4())
        session: dict = {
            "session_id": session_id,
            "user_id": str(identity.user_id),
            "session_type": "writing",
            "state": "writing",
            "theme": theme_obj.theme,
            "writing_task_text": task,  # submit_writing reads this directly
            "text": theme_obj.theme,  # fallback context for review_writing
            "target_lang": str(profile.target_lang),
            "native_lang": str(profile.native_lang),
            "level": str(profile.level),
            "questions": [],
            "question_count": 0,
            "user_answers": [],
            "feedback": "",
            "writing_text": "",
            "writing_feedback": "",
        }
        await self._store.save(session, user_id=str(identity.user_id))
        return WritingSessionResult(session_id=session_id, task=task, theme=theme_obj.theme)
