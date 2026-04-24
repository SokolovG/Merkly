"""Writing use case — standalone theme-based writing sessions.

Two flows share one use case:
- Standalone (/writing command): user picks an exam-style theme from the DB pool
  → WritingUseCase.get_themes + WritingUseCase.start
- Session-backed (post-reading/listening writing): article text is already in
  the Redis session; the controller calls agent.generate_writing_task directly.
  That path stays thin and does not need a separate use case.
"""

import uuid
from dataclasses import dataclass

from backend.src.application.agent.core import LessonAgent
from backend.src.domain.entities import Identity, UserProfile, WritingTheme
from backend.src.domain.ports.writing_theme_repo import IWritingThemeRepository
from backend.src.infrastructure.exceptions import InternalServerError, NotFoundError
from backend.src.infrastructure.session_store import RedisSessionStore


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
        """
        try:
            return await self._theme_repo.get_unseen(
                user_id=profile.id,
                target_lang=str(profile.target_lang),
                level=profile.level,
                limit=limit,
            )
        except Exception as exc:
            raise InternalServerError(
                message="Failed to fetch writing themes",
                details={"user_id": str(profile.id)},
            ) from exc

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

        try:
            await self._theme_repo.mark_seen(user_id=profile.id, theme_id=theme_id)
        except Exception:
            pass  # non-critical — don't fail the session over history tracking

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
