import logging

from aiogram import Router
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.domain.exceptions import AppError, WordCaptureError
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
from src.infrastructure.telegram.messages import (
    card_saved,
    card_saved_no_backend,
    complete_setup,
    looking_up,
    word_capture_error,
    word_capture_failed,
    word_empty,
)

logger = logging.getLogger(__name__)

word_router = Router()


@word_router.message(lambda msg: msg.text is not None and msg.text.startswith("+"))
async def handle_word_capture(
    message: Message,
    agent: FromDishka[LessonAgent],
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    if message.from_user is None:
        return
    user_id = message.from_user.id
    word = (message.text or "")[1:].strip()

    if not word:
        await message.reply(word_empty(), parse_mode="HTML")
        return

    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        return

    await message.reply(looking_up(word), parse_mode="HTML")

    try:
        card = await agent.capture_word(
            word=word,
            target_lang=profile.target_lang,
            native_lang=profile.native_lang,
        )
    except WordCaptureError:
        await message.reply(word_capture_failed(word), parse_mode="HTML")
        return
    except AppError:
        await message.reply(word_capture_error(), parse_mode="HTML")
        return

    display_word = f"{card.article} {card.word}" if card.article else card.word
    if card.backend_id:
        text = card_saved(display_word, card.translation, card.example_sentence)
    else:
        text = card_saved_no_backend(display_word, card.translation, card.example_sentence)
    await message.reply(text, parse_mode="HTML")
