import asyncio
import os
from html import escape

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.application.listening_refill_service import ListeningRefillService
from src.application.listening_service import ListeningAgent
from src.domain.enums import ActivityType, Platform
from src.domain.ports.listening_history_repo import IListeningHistoryRepository
from src.domain.ports.listening_pool_repo import IListeningPoolRepository
from src.domain.ports.session_history_repo import ISessionHistoryRepository
from src.infrastructure.audio import AudioService
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.database.repositories.identity_repo import IdentityRepository
from src.infrastructure.telegram import messages

logger = structlog.get_logger(__name__)

router = Router()

_pending_listening: dict[int, dict] = {}


@router.message(Command("listen"))
async def cmd_listen(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    identity_repo: FromDishka[IdentityRepository],
    listening_service: FromDishka[ListeningAgent],
    session_history_repo: FromDishka[ISessionHistoryRepository],
    listening_pool_repo: FromDishka[IListeningPoolRepository],
    listening_history_repo: FromDishka[IListeningHistoryRepository],
    listening_refill_service: FromDishka[ListeningRefillService],
    audio_service: FromDishka[AudioService],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    identity = await identity_repo.get_by_platform(Platform.TELEGRAM, str(user_id))
    profile = await profile_repo.get_by_id(identity.user_id) if identity else None

    if not profile:
        await message.answer(messages.no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("cmd_listen", messenger_id=user_id)

    if ActivityType.LISTENING not in profile.learning_strategy:
        await message.answer(messages.listening_disabled())
        return

    await message.answer(messages.listening_fetching())

    # --- Listening Pool: try pool first (skip stale entries, try once more before live) ---
    pooled = await listening_pool_repo.get_oldest(profile.id, str(profile.target_lang))
    if pooled and await session_history_repo.has_seen(profile.id, pooled.episode_url):
        # Stale entry — discard and try the next one before falling through to live
        await listening_pool_repo.mark_served(pooled.id)
        logger.info("cmd_listen_pool_stale", messenger_id=user_id)
        pooled = await listening_pool_repo.get_oldest(profile.id, str(profile.target_lang))

    if pooled and not await session_history_repo.has_seen(profile.id, pooled.episode_url):
        # Pool hit — skip Whisper + podcast search
        await listening_pool_repo.mark_served(pooled.id)
        logger.info("cmd_listen_pool_hit", messenger_id=user_id)

        audio_path = await audio_service.download(pooled.episode_url, profile.episode_duration_min)
        try:
            with open(audio_path, "rb") as f:
                await message.answer_audio(
                    BufferedInputFile(f.read(), filename="lesson.mp3"),
                    caption=f"🎧 {escape(pooled.title)}",
                )
        finally:
            os.unlink(audio_path)

        await session_history_repo.record(profile.id, pooled.episode_url, ActivityType.LISTENING)

        _pending_listening[user_id] = {
            "transcript": pooled.transcript,
            "questions": pooled.questions,
            "level": profile.level,
            "native_lang": profile.native_lang,
            "target_lang": profile.target_lang,
            "episode_url": pooled.episode_url,
        }
    else:
        # Pool miss — full live path (Whisper + podcast search)
        if pooled:
            await listening_pool_repo.mark_served(pooled.id)  # discard stale
        logger.info("cmd_listen_pool_miss", messenger_id=user_id)

        try:
            lesson = await listening_service.prepare_lesson(profile)
        except Exception as e:
            logger.error("listening_lesson_failed", error=str(e))
            await message.answer(f"Couldn't prepare listening lesson: {e}\nTry again later.")
            return

        try:
            with open(lesson.audio_path, "rb") as f:
                await message.answer_audio(
                    BufferedInputFile(f.read(), filename="lesson.mp3"),
                    caption=f"🎧 {escape(lesson.title)}",
                )
        finally:
            os.unlink(lesson.audio_path)

        await session_history_repo.record(profile.id, lesson.episode_url, ActivityType.LISTENING)
        await listening_history_repo.record(
            profile.id, lesson.episode_url, str(profile.target_lang)
        )
        await message.answer(messages.listening_transcribing())  # T23: live path only

        _pending_listening[user_id] = {
            "transcript": lesson.transcript,
            "questions": lesson.questions,
            "level": profile.level,
            "native_lang": profile.native_lang,
            "target_lang": profile.target_lang,
            "episode_url": lesson.episode_url,
        }

    # Build questions text (shared: both paths write to _pending_listening above)
    questions = _pending_listening[user_id]["questions"]
    questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    await message.answer(messages.listening_questions(questions_text))

    # Eager refill (non-blocking — fire and forget)
    async def _refill_with_log() -> None:
        try:
            await listening_refill_service.refill_if_needed(profile)
        except Exception as exc:
            logger.error("listening_pool_eager_refill_failed", error=str(exc))

    asyncio.create_task(_refill_with_log())


@router.message(
    lambda msg: (
        msg.from_user is not None
        and msg.text is not None
        and not msg.text.startswith("/")
        and msg.from_user.id in _pending_listening
    )
)
async def handle_listening_answer(
    message: Message,
    agent: FromDishka[LessonAgent],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    ctx = _pending_listening.pop(user_id, None)

    if not ctx or not message.text:
        return

    feedback, _ = await agent.review_answers(
        article_text=ctx["transcript"],
        questions=ctx["questions"],
        answers=[message.text],
        level=ctx["level"],
        native_lang=ctx["native_lang"],
        target_lang=ctx["target_lang"],
    )

    await message.answer(
        f"📝 <b>Feedback:</b>\n\n{escape(feedback)}",
        parse_mode="HTML",
    )
