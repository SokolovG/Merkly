"""Session controller — reading and listening lesson flows.

State lives in Redis (session:{session_id}, TTL 15 min).
All routes require Authorization: Bearer {BACKEND_API_KEY}.
"""

import uuid
from datetime import UTC, datetime

from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.params import Parameter

from backend.src.application.agent.core import LessonAgent
from backend.src.application.listening_service import ListeningAgent
from backend.src.domain.enums import ActivityType, Platform
from backend.src.domain.ports.listening_pool_repo import IListeningPoolRepository
from backend.src.domain.ports.session_history_repo import ISessionHistoryRepository
from backend.src.infrastructure.database.repositories.article_pool_repo import ArticlePoolRepository
from backend.src.infrastructure.database.repositories.identity_repo import IdentityRepository
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.database.repositories.session_history_repo import (
    SessionHistoryRepository,
)
from backend.src.infrastructure.session_store import RedisSessionStore
from backend.src.presentation.converters import vocab_card_to_dto
from backend.src.presentation.dto.session.requests import (
    StartListeningSessionRequest,
    StartReadingSessionRequest,
    SubmitAnswerRequest,
    SubmitWritingRequest,
)
from backend.src.presentation.dto.session.responses import (
    ActiveSessionResponse,
    AnswerResponse,
    StartSessionResponse,
    WritingResponse,
)
from backend.src.presentation.responses.base import SuccessResponse


class SessionController(Controller):
    path = "/sessions"

    @inject
    @post("/reading/start")
    async def start_reading_session(
        self,
        data: StartReadingSessionRequest,
        identity_repo: FromDishka[IdentityRepository],
        profile_repo: FromDishka[ProfileRepository],
        article_pool: FromDishka[ArticlePoolRepository],
        session_history: FromDishka[SessionHistoryRepository],
        agent: FromDishka[LessonAgent],
        store: FromDishka[RedisSessionStore],
    ) -> SuccessResponse:
        """Resolve contact → profile → fetch article (pool or live) →
        create Redis session with state=questions → return title+content+questions."""
        try:
            platform_enum = Platform(data.platform)
        except ValueError:
            raise NotFoundException(detail=f"Unknown platform: {data.platform!r}") from None

        identity = await identity_repo.get_by_platform(platform_enum, data.contact_id)
        if identity is None:
            raise NotFoundException(
                detail=f"No identity for {data.platform}:{data.contact_id}"
            ) from None

        profile = await profile_repo.get_by_id(identity.user_id)
        if profile is None:
            raise NotFoundException(
                detail=f"Profile not found for user_id={identity.user_id}"
            ) from None

        # Try pool first; fall back to live fetch
        pool_article = await article_pool.get_oldest(profile.id, str(profile.target_lang))
        if pool_article is not None:
            await article_pool.mark_served(pool_article.id)
            title = pool_article.title
            url = pool_article.url
            text = pool_article.text
            questions = list(pool_article.questions)
        else:
            title, url, text, questions = await agent.prepare_reading_lesson(
                level=profile.level,
                goal=str(profile.goal),
                native_lang=str(profile.native_lang),
                target_lang=str(profile.target_lang),
                recent_topics=[],
                question_count=profile.question_count,
            )

        await session_history.record(profile.id, url, ActivityType.READING)

        session_id = str(uuid.uuid4())
        session: dict = {
            "session_id": session_id,
            "user_id": str(identity.user_id),
            "session_type": "reading",
            "state": "questions",
            "target_lang": str(profile.target_lang),
            "title": title,
            "url": url,
            "text": text[:2000],
            "questions": questions,
            "user_answers": [],
            "feedback": None,
            "writing_text": None,
            "writing_feedback": None,
            "level": profile.level,
            "native_lang": str(profile.native_lang),
            "question_count": len(questions),
            "audio_url": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await store.save(session, user_id=str(identity.user_id))

        return SuccessResponse(
            data=StartSessionResponse(
                session_id=session_id,
                session_type="reading",
                title=title,
                content=text,
                questions=questions,
            ),
            message="Reading session started",
        )

    @inject
    @post("/listening/start")
    async def start_listening_session(
        self,
        data: StartListeningSessionRequest,
        identity_repo: FromDishka[IdentityRepository],
        profile_repo: FromDishka[ProfileRepository],
        listening_pool: FromDishka[IListeningPoolRepository],
        session_history: FromDishka[ISessionHistoryRepository],
        listening_agent: FromDishka[ListeningAgent],
        store: FromDishka[RedisSessionStore],
    ) -> SuccessResponse:
        """Resolve contact → profile → fetch episode (pool or live) →
        create Redis session with state=questions → return title+questions+audio_url."""
        try:
            platform_enum = Platform(data.platform)
        except ValueError:
            raise NotFoundException(detail=f"Unknown platform: {data.platform!r}") from None

        identity = await identity_repo.get_by_platform(platform_enum, data.contact_id)
        if identity is None:
            raise NotFoundException(
                detail=f"No identity for {data.platform}:{data.contact_id}"
            ) from None

        profile = await profile_repo.get_by_id(identity.user_id)
        if profile is None:
            raise NotFoundException(
                detail=f"Profile not found for user_id={identity.user_id}"
            ) from None

        # Try pool first; fall back to live Whisper transcription
        pool_lesson = await listening_pool.get_oldest(profile.id, str(profile.target_lang))
        if pool_lesson is not None:
            await listening_pool.mark_served(pool_lesson.id)
            title = pool_lesson.title
            episode_url = pool_lesson.episode_url
            questions = list(pool_lesson.questions)
            content = pool_lesson.transcript[:2000]
        else:
            lesson = await listening_agent.prepare_lesson(profile)
            title = lesson.title
            episode_url = lesson.episode_url
            questions = lesson.questions
            content = lesson.transcript[:2000]

        await session_history.record(profile.id, episode_url, ActivityType.LISTENING)

        session_id = str(uuid.uuid4())
        session: dict = {
            "session_id": session_id,
            "user_id": str(identity.user_id),
            "session_type": "listening",
            "state": "questions",
            "target_lang": str(profile.target_lang),
            "title": title,
            "url": episode_url,
            "text": content,
            "questions": questions,
            "user_answers": [],
            "feedback": None,
            "writing_text": None,
            "writing_feedback": None,
            "level": profile.level,
            "native_lang": str(profile.native_lang),
            "question_count": len(questions),
            "audio_url": episode_url,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await store.save(session, user_id=str(identity.user_id))

        return SuccessResponse(
            data=StartSessionResponse(
                session_id=session_id,
                session_type="listening",
                title=title,
                content=content,
                questions=questions,
                audio_url=episode_url,
            ),
            message="Listening session started",
        )

    @inject
    @get("/active")
    async def get_active_session(
        self,
        identity_repo: FromDishka[IdentityRepository],
        store: FromDishka[RedisSessionStore],
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
    ) -> SuccessResponse:
        """Look up Redis for any active session for this contact."""
        _empty = SuccessResponse(
            data=ActiveSessionResponse(session_id=None, state=None), message="No active session"
        )

        try:
            platform_enum = Platform(platform)
        except ValueError:
            return _empty

        identity = await identity_repo.get_by_platform(platform_enum, contact_id)
        if identity is None:
            return _empty

        sid = await store.get_active_session_id(str(identity.user_id))
        if sid is None:
            return _empty

        session = await store.get(sid)
        if session is None:
            return _empty

        return SuccessResponse(
            data=ActiveSessionResponse(session_id=sid, state=session["state"]),
            message="Active session found",
        )

    @inject
    @post("/{session_id:str}/answer")
    async def submit_answer(
        self,
        session_id: str,
        data: SubmitAnswerRequest,
        profile_repo: FromDishka[ProfileRepository],
        agent: FromDishka[LessonAgent],
        store: FromDishka[RedisSessionStore],
    ) -> SuccessResponse:
        """Accumulate answers; once all received, run LLM review and return feedback."""
        session = await store.get(session_id)
        if session is None:
            raise NotFoundException(detail="Session expired or not found") from None

        session["user_answers"].extend(data.answers)
        answered = len(session["user_answers"])
        total = session["question_count"]

        if answered < total:
            await store.save(session, user_id=session["user_id"])
            return SuccessResponse(
                data=AnswerResponse(feedback="", writing_available=False, cards=[]),
                message="Answer recorded",
            )

        feedback, _ = await agent.review_answers(
            article_text=session["text"],
            questions=session["questions"],
            answers=session["user_answers"],
            level=session["level"],
            native_lang=session["native_lang"],
            target_lang=session["target_lang"],
        )

        try:
            uid = uuid.UUID(session["user_id"])
            profile = await profile_repo.get_by_id(uid)
            writing_available = (
                profile is not None and ActivityType.WRITING in profile.learning_strategy
            )
        except ValueError:
            writing_available = False

        session["state"] = "writing" if writing_available else "complete"
        session["feedback"] = feedback
        await store.save(session, user_id=session["user_id"])

        return SuccessResponse(
            data=AnswerResponse(feedback=feedback, writing_available=writing_available, cards=[]),
            message="Answers reviewed",
        )

    @inject
    @post("/{session_id:str}/writing")
    async def submit_writing(
        self,
        session_id: str,
        data: SubmitWritingRequest,
        agent: FromDishka[LessonAgent],
        store: FromDishka[RedisSessionStore],
    ) -> SuccessResponse:
        """Run writing review against the article context and return feedback + vocab cards."""
        session = await store.get(session_id)
        if session is None:
            raise NotFoundException(detail="Session expired or not found") from None

        if session["state"] != "writing":
            raise ClientException(
                detail="Session is not in writing state",
                status_code=409,
            )

        writing_task = await agent.generate_writing_task(
            article_text=session["text"],
            target_lang=session["target_lang"],
            level=session["level"],
        )
        feedback, cards = await agent.review_writing(
            writing_task=writing_task,
            user_writing=data.text,
            level=session["level"],
            native_lang=session["native_lang"],
            target_lang=session["target_lang"],
        )

        session["state"] = "complete"
        session["writing_text"] = data.text
        session["writing_feedback"] = feedback
        await store.save(session, user_id=session["user_id"])

        return SuccessResponse(
            data=WritingResponse(
                feedback=feedback,
                cards=[vocab_card_to_dto(c) for c in cards],
            ),
            message="Writing reviewed",
        )
