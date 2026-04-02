import logging
from html import escape

from aiogram import Router
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.domain.exceptions import AppError, WordCaptureError
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository

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
        await message.reply("Please add a word after +, e.g. <b>+Brot</b>", parse_mode="HTML")
        return

    logger.info("User %d: +%s", user_id, word)

    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply("Please complete setup first — type /start")
        return

    await message.reply("Looking up <b>" + escape(word) + "</b>... ⏳", parse_mode="HTML")

    try:
        card = await agent.capture_word(
            word=word,
            target_lang=profile.target_lang,
            native_lang=profile.native_lang,
        )
    except WordCaptureError as e:
        logger.warning("capture_word failed for user %s word '%s': %s", user_id, word, e)
        await message.reply(
            f"Couldn't generate a card for <b>{escape(word)}</b>. "
            "Try again or check the spelling.",
            parse_mode="HTML",
        )
        return
    except AppError as e:
        logger.error("capture_word infra error for user %s: %s", user_id, e)
        await message.reply(
            "Something went wrong adding the card. Please try again.",
            parse_mode="HTML",
        )
        return

    display_word = f"{card.article} {card.word}" if card.article else card.word
    lines = [
        f"✅ <b>{escape(display_word)}</b> — {escape(card.translation)}",
        f"<i>{escape(card.example_sentence)}</i>",
    ]
    if card.backend_id:
        lines.append("📥 Saved to your deck")
    else:
        lines.append("⚠️ Card saved locally (deck not connected)")

    await message.reply("\n".join(lines), parse_mode="HTML")
