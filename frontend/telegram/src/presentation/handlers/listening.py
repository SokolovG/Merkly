"""Listening lesson handler — thin I/O, calls BackendClient.

Audio file delivery (BufferedInputFile) is deferred to 19-06 when backend
returns a downloadable audio_url. This plan delivers title + questions.
"""

from html import escape

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient
from src.presentation import messages

router = Router()
logger = structlog.get_logger(__name__)

_PLATFORM = "telegram"


@router.message(Command("listen"))
async def cmd_listen(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    contact_id = str(message.from_user.id)  # type: ignore[union-attr]
    structlog.contextvars.bind_contextvars(contact_id=contact_id)
    logger.info("cmd_listen")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_listening_session(_PLATFORM, contact_id)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    # Deliver episode info. Full audio streaming (downloading audio_url and sending
    # BufferedInputFile) is implemented in 19-06 once the backend provides audio_url.
    header = f"🎧 <b>{escape(result.title)}</b>"
    if result.audio_url:
        header += f"\n\n<i>Audio: {escape(result.audio_url)}</i>"

    await message.answer(header, parse_mode="HTML")

    questions_text = "\n".join(f"{i}. {escape(q)}" for i, q in enumerate(result.questions, 1))
    await message.answer(
        f"❓ <b>Questions:</b>\n\n{questions_text}\n\n"
        f"Send your answers as one message (answer all {len(result.questions)}).",
        parse_mode="HTML",
    )
