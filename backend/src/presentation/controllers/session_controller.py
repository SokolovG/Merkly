"""Session controller — thin transport layer.

Resolves identity, delegates to StartSessionUseCase, returns typed responses.
All business logic lives in the use case.
"""

import uuid

from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.params import Parameter

from backend.src.application.agent.core import LessonAgent
from backend.src.application.use_cases.resolve_user import UserResolverUseCase
from backend.src.application.use_cases.start_session import StartSessionUseCase
from backend.src.domain.enums import ActivityType, Platform
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.exceptions import ApiException
from backend.src.infrastructure.session_store import RedisSessionStore
from backend.src.presentation.converters import vocab_card_to_dto
from backend.src.presentation.dto.session.requests import (
    StartListeningSessionRequest,
    StartReadingSessionRequest,
    StartSessionRequest,
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
    @post("/start")
    async def start_session(
        self,
        data: StartSessionRequest,
        resolver: FromDishka[UserResolverUseCase],
        session_uc: FromDishka[StartSessionUseCase],
    ) -> SuccessResponse:
        """Auto-pick activity from profile.learning_strategy (READING > LISTENING)."""
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await session_uc.execute_auto(ctx.profile, ctx.identity)
        return SuccessResponse(
            data=StartSessionResponse(
                session_id=result.session_id,
                session_type=result.session_type,
                title=result.title,
                content=result.content,
                questions=result.questions,
                audio_url=result.audio_url,
            ),
            message="Session started",
        )

    @inject
    @post("/reading/start")
    async def start_reading_session(
        self,
        data: StartReadingSessionRequest,
        resolver: FromDishka[UserResolverUseCase],
        session_uc: FromDishka[StartSessionUseCase],
    ) -> SuccessResponse:
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await session_uc.execute_reading(ctx.profile, ctx.identity)
        return SuccessResponse(
            data=StartSessionResponse(
                session_id=result.session_id,
                session_type=result.session_type,
                title=result.title,
                content=result.content,
                questions=result.questions,
            ),
            message="Reading session started",
        )

    @inject
    @post("/listening/start")
    async def start_listening_session(
        self,
        data: StartListeningSessionRequest,
        resolver: FromDishka[UserResolverUseCase],
        session_uc: FromDishka[StartSessionUseCase],
    ) -> SuccessResponse:
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await session_uc.execute_listening(ctx.profile, ctx.identity)
        return SuccessResponse(
            data=StartSessionResponse(
                session_id=result.session_id,
                session_type=result.session_type,
                title=result.title,
                content=result.content,
                questions=result.questions,
                audio_url=result.audio_url,
            ),
            message="Listening session started",
        )

    @inject
    @get("/active")
    async def get_active_session(
        self,
        resolver: FromDishka[UserResolverUseCase],
        store: FromDishka[RedisSessionStore],
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
    ) -> SuccessResponse:
        """Look up Redis for any active session for this contact.

        Returns empty response (not 404) when platform/identity unknown —
        callers use session_id=None as the sentinel.
        """
        _empty = SuccessResponse(
            data=ActiveSessionResponse(session_id=None, state=None), message="No active session"
        )

        try:
            platform_enum = Platform(platform)
        except ValueError:
            return _empty

        try:
            ctx = await resolver.resolve(platform_enum, contact_id)
        except ApiException:
            return _empty

        sid = await store.get_active_session_id(str(ctx.identity.user_id))
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
