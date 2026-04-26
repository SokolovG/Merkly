import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.src.application.agent.core import LessonAgent
from backend.src.application.background_refiller import BackgroundRefiller
from backend.src.application.listening_service import ListeningAgent
from backend.src.application.ports.session_store import SessionStore
from backend.src.domain.entities import Identity, UserProfile
from backend.src.domain.enums import ActivityType
from backend.src.domain.ports.listening_pool_repo import IListeningPoolRepository
from backend.src.domain.ports.session_history_repo import ISessionHistoryRepository
from backend.src.domain.session import SessionState
from backend.src.infrastructure.database.repositories.article_pool_repo import ArticlePoolRepository

_TEXT_PREVIEW_CHARS = 2000


@dataclass(frozen=True)
class SessionStartResult:
    session_id: str
    session_type: str  # "reading" | "listening"
    title: str
    content: str
    questions: list[str]
    audio_url: str | None = None


class StartSessionUseCase:
    def __init__(
        self,
        article_pool: ArticlePoolRepository,
        session_history: ISessionHistoryRepository,
        agent: LessonAgent,
        store: SessionStore,
        listening_pool: IListeningPoolRepository,
        listening_agent: ListeningAgent,
        refiller: BackgroundRefiller,
    ) -> None:
        self._article_pool = article_pool
        self._session_history = session_history
        self._agent = agent
        self._store = store
        self._listening_pool = listening_pool
        self._listening_agent = listening_agent
        self._refiller = refiller

    def _use_listening(self, profile: UserProfile) -> bool:
        return (
            ActivityType.LISTENING in profile.learning_strategy
            and ActivityType.READING not in profile.learning_strategy
        )

    async def execute_auto(self, profile: UserProfile, identity: Identity) -> SessionStartResult:
        if self._use_listening(profile):
            return await self.execute_listening(profile, identity)
        return await self.execute_reading(profile, identity)

    async def execute_reading(self, profile: UserProfile, identity: Identity) -> SessionStartResult:
        pool_article = await self._article_pool.get_oldest(profile.id, str(profile.target_lang))
        if pool_article is not None:
            await self._article_pool.mark_served(pool_article.id)
            self._refiller.schedule_article_refill(profile)
            title, url, text, questions = (
                pool_article.title,
                pool_article.url,
                pool_article.text,
                list(pool_article.questions),
            )
        else:
            title, url, text, questions = await self._agent.prepare_reading_lesson(
                level=profile.level,
                goal=str(profile.goal),
                native_lang=str(profile.native_lang),
                target_lang=str(profile.target_lang),
                recent_topics=[],
                question_count=profile.question_count,
            )
            self._refiller.schedule_article_refill(profile)

        await self._session_history.record(profile.id, url, ActivityType.READING)
        session_id = str(uuid.uuid4())
        await self._store.save(
            _build_session(
                session_id=session_id,
                user_id=str(identity.user_id),
                session_type="reading",
                profile=profile,
                title=title,
                url=url,
                text=text,
                questions=questions,
            ),
            user_id=str(identity.user_id),
        )
        return SessionStartResult(
            session_id=session_id,
            session_type="reading",
            title=title,
            content=text,
            questions=questions,
        )

    async def execute_listening(
        self, profile: UserProfile, identity: Identity
    ) -> SessionStartResult:
        pool_lesson = await self._listening_pool.get_oldest(profile.id, str(profile.target_lang))
        if pool_lesson is not None:
            await self._listening_pool.mark_served(pool_lesson.id)
            self._refiller.schedule_listening_refill(profile)
            title = pool_lesson.title
            episode_url = pool_lesson.episode_url
            questions = list(pool_lesson.questions)
            content = pool_lesson.transcript[:_TEXT_PREVIEW_CHARS]
        else:
            lesson = await self._listening_agent.prepare_lesson(profile)
            title = lesson.title
            episode_url = lesson.episode_url
            questions = lesson.questions
            self._refiller.schedule_listening_refill(profile)
            content = lesson.transcript[:_TEXT_PREVIEW_CHARS]

        await self._session_history.record(profile.id, episode_url, ActivityType.LISTENING)
        session_id = str(uuid.uuid4())
        await self._store.save(
            _build_session(
                session_id=session_id,
                user_id=str(identity.user_id),
                session_type="listening",
                profile=profile,
                title=title,
                url=episode_url,
                text=content,
                questions=questions,
                audio_url=episode_url,
            ),
            user_id=str(identity.user_id),
        )
        return SessionStartResult(
            session_id=session_id,
            session_type="listening",
            title=title,
            content=content,
            questions=questions,
            audio_url=episode_url,
        )


def _build_session(
    *,
    session_id: str,
    user_id: str,
    session_type: str,
    profile: UserProfile,
    title: str,
    url: str,
    text: str,
    questions: list[str],
    audio_url: str | None = None,
) -> SessionState:
    return SessionState(
        session_id=session_id,
        user_id=user_id,
        session_type=session_type,
        state="questions",
        target_lang=str(profile.target_lang),
        title=title,
        url=url,
        text=text[:_TEXT_PREVIEW_CHARS],
        questions=questions,
        user_answers=[],
        feedback=None,
        writing_text=None,
        writing_feedback=None,
        level=profile.level,
        native_lang=str(profile.native_lang),
        question_count=len(questions),
        audio_url=audio_url,
        created_at=datetime.now(UTC).isoformat(),
    )
