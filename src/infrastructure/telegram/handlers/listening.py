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
from src.infrastructure.telegram import messages

logger = getLogger(__name__)

router = Router()

_pending_listening: dict[int, dict] = {}


@router.message(Command("listen"))
async def cmd_listen(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    listening_service: FromDishka[ListeningAgent],
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
        logger.error(e)
        await message.answer(f"Couldn't prepare listening lesson: {e}\nTry again later.")
        return

    with open(lesson.audio_path, "rb") as f:
        await message.answer_audio(
            BufferedInputFile(f.read(), filename="lesson.mp3"),
            caption=f"🎧 {escape(lesson.title)}",
        )

    await message.answer(messages.listening_transcribing())

    _pending_listening[user_id] = {
        "transcript": lesson.transcript,
        "questions": lesson.questions,
        "level": profile.level,
        "native_lang": profile.native_lang,
        "target_lang": profile.target_lang,
    }

    questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(lesson.questions))
    await message.answer(messages.listening_questions(questions_text))


@router.message(lambda msg: msg.from_user is not None and msg.from_user.id in _pending_listening)
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
