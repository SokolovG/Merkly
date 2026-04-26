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
from backend.src.application.use_cases.writing_use_case import WritingUseCase
from backend.src.domain.enums import ActivityType, Platform
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.exceptions import ApiException
from backend.src.infrastructure.session_store import RedisSessionStore
from backend.src.presentation.converters import vocab_card_to_dto
from backend.src.presentation.dto.session.requests import (
    StartListeningSessionRequest,
    StartReadingSessionRequest,
    StartSessionRequest,
    StartWritingSessionRequest,
    SubmitAnswerRequest,
    SubmitWritingRequest,
)
from backend.src.presentation.dto.session.responses import (
    ActiveSessionResponse,
    AnswerResponse,
    StartSessionResponse,
    StartWritingSessionResponse,
    WritingResponse,
    WritingThemeDTO,
    WritingThemesResponse,
)
from backend.src.presentation.responses.base import SuccessResponse


class SessionController(Controller):
    path = "/sessions"

    @post("/start")
    @inject
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

    @post("/reading/start")
    @inject
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

    @post("/listening/start")
    @inject
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

    @get("/active")
    @inject
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

    @get("/writing/themes")
    @inject
    async def get_writing_themes(
        self,
        resolver: FromDishka[UserResolverUseCase],
        writing_uc: FromDishka[WritingUseCase],
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
        count: int = Parameter(query="count", default=1),
    ) -> SuccessResponse:
        """Return writing topics from the pool suited to user's language + level.

        count=1 (default) for the random-theme flow.
        count=5 for the choose-theme picker.
        """
        try:
            platform_enum = Platform(platform)
        except ValueError as e:
            raise ApiException(
                message=f"Unknown platform: {platform!r}",
                status_code=400,
                error_code="VALIDATION_ERROR",
            ) from e

        ctx = await resolver.resolve(platform_enum, contact_id)
        themes = await writing_uc.get_themes(ctx.profile, limit=count)
        return SuccessResponse(
            data=WritingThemesResponse(
                themes=[WritingThemeDTO(id=str(t.id), theme=t.theme) for t in themes]
            ),
            message="Writing themes fetched",
        )

    @post("/writing/start")
    @inject
    async def start_writing_session(
        self,
        data: StartWritingSessionRequest,
        resolver: FromDishka[UserResolverUseCase],
        writing_uc: FromDishka[WritingUseCase],
    ) -> SuccessResponse:
        """Generate a standalone writing task for the given theme and create a writing session."""
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await writing_uc.start(
            ctx.profile, ctx.identity, theme_id=uuid.UUID(data.theme_id), mode=data.mode
        )
        return SuccessResponse(
            data=StartWritingSessionResponse(
                session_id=result.session_id,
                task=result.task,
                theme=result.theme,
            ),
            message="Writing session started",
        )

    @post("/{session_id:str}/answer")
    @inject
    async def submit_answer(
        self,
        session_id: str,
        data: SubmitAnswerRequest,
        profile_repo: FromDishka[ProfileRepository],
        agent: FromDishka[LessonAgent],
        store: FromDishka[RedisSessionStore],
    ) -> SuccessResponse:
        """Run LLM review on the submitted answers and return feedback.

        The Telegram frontend sends all answers in a single message, so we always
        review immediately rather than accumulating across multiple requests.
        """
        session = await store.get(session_id)
        if session is None:
            raise NotFoundException(detail="Session expired or not found") from None

        session["user_answers"].extend(data.answers)
        await store.save(session, user_id=session["user_id"])

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

    @post("/{session_id:str}/writing")
    @inject
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

        # Standalone writing sessions pre-generate the task and store it.
        # Article-backed sessions generate it here from the article text.
        writing_task = session.get("writing_task_text") or await agent.generate_writing_task(
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
