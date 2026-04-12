import contextlib
import os
from html import escape
from logging import getLogger

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.application.listening_service import ListeningAgent
from src.domain.enums import ActivityType
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.database.repositories.session_history_repo import SessionHistoryRepository
from src.infrastructure.telegram import messages

logger = getLogger(__name__)

router = Router()

_pending_listening: dict[int, dict] = {}


@router.message(Command("listen"))
async def cmd_listen(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    listening_service: FromDishka[ListeningAgent],
    session_history_repo: FromDishka[SessionHistoryRepository],
) -> None:
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)

    if not profile:
        await message.answer(messages.no_profile())
        return

    if ActivityType.LISTENING not in profile.learning_strategy:
        await message.answer(messages.listening_disabled())
        return

    await message.answer(messages.listening_fetching())

    try:
        lesson = await listening_service.prepare_lesson(profile)
    except Exception as e:
        logger.error("Failed to prepare listening lesson: %s", e, exc_info=True)
        await message.answer(f"Couldn't prepare listening lesson: {e}\nTry again later.")
        return

    # Dedup: retry once if this episode URL was already served to this user
    if await session_history_repo.has_seen(profile.id, lesson.episode_url):
        with contextlib.suppress(Exception):
            lesson = await listening_service.prepare_lesson(profile)

    try:
        with open(lesson.audio_path, "rb") as f:
            await message.answer_audio(
                BufferedInputFile(f.read(), filename="lesson.mp3"),
                caption=f"🎧 {escape(lesson.title)}",
            )
    finally:
        os.unlink(lesson.audio_path)

    await session_history_repo.record(profile.id, lesson.episode_url, ActivityType.LISTENING)
    await message.answer(messages.listening_transcribing())

    _pending_listening[user_id] = {
        "transcript": lesson.transcript,
        "questions": lesson.questions,
        "level": profile.level,
        "native_lang": profile.native_lang,
        "target_lang": profile.target_lang,
        "episode_url": lesson.episode_url,
    }

    questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(lesson.questions))
    await message.answer(messages.listening_questions(questions_text))


@router.message(
    lambda msg: (
        msg.from_user is not None
        and msg.text is not None
        and msg.from_user.id in _pending_listening
    )
)
async def handle_listening_answer(
    message: Message,
    agent: FromDishka[LessonAgent],
) -> None:
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
