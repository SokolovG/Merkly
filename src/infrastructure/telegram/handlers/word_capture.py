import contextlib

import structlog
from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.domain.entities import VocabCard
from src.domain.exceptions import AppError, WordCaptureError
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.telegram.messages import (
    ask_for_context,
    card_saved,
    card_saved_no_backend,
    complete_setup,
    looking_up,
    regenerating,
    word_capture_error,
    word_capture_failed,
    word_empty,
)

logger = structlog.get_logger(__name__)

word_router = Router()

# Pending regenerate state: user_id → {word, card, target_lang, native_lang, waiting_context?}
_pending_regen: dict[int, dict] = {}


def _word_card_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Wrong meaning?", callback_data="wordcard:regen"),
            ]
        ]
    )


class _WaitingRegenContext(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        uid = message.from_user.id if message.from_user else None
        return uid is not None and _pending_regen.get(uid, {}).get("waiting_context") is True


@word_router.message(lambda msg: msg.text is not None and msg.text.startswith("+"))
async def handle_word_capture(
    message: Message,
    agent: FromDishka[LessonAgent],
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None:
        return
    user_id = message.from_user.id

    raw = (message.text or "")[1:].strip()
    if "/" in raw:
        word, ctx_str = raw.split("/", 1)
        word = word.strip()
        context: str | None = ctx_str.strip() or None
    else:
        word, context = raw, None

    if not word:
        await message.reply(word_empty(), parse_mode="HTML")
        return

    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("word_capture", messenger_id=user_id)

    deck_name = next(
        (d.name for d in profile.decks if d.backend_id == profile.active_deck_id),
        None,
    )

    await message.reply(looking_up(word), parse_mode="HTML")

    try:
        card = await agent.capture_word(
            word=word,
            target_lang=profile.target_lang,
            native_lang=profile.native_lang,
            context=context,
            deck_id=profile.active_deck_id or None,
        )
    except WordCaptureError:
        await message.reply(word_capture_failed(word), parse_mode="HTML")
        return
    except AppError:
        await message.reply(word_capture_error(), parse_mode="HTML")
        return

    _pending_regen[user_id] = {
        "word": word,
        "card": card,
        "target_lang": profile.target_lang,
        "native_lang": profile.native_lang,
        "active_deck_id": profile.active_deck_id,
        "deck_name": deck_name,
    }

    display_word = f"{card.article} {card.word}" if card.article else card.word
    text = (
        card_saved(
            display_word, card.translation, card.example_sentence, card.grammar_note, deck_name
        )
        if card.backend_id
        else card_saved_no_backend(
            display_word, card.translation, card.example_sentence, card.grammar_note, deck_name
        )
    )
    await message.reply(text, parse_mode="HTML", reply_markup=_word_card_keyboard())


@word_router.callback_query(F.data == "wordcard:regen")
async def handle_wordcard_regen(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    ctx = _pending_regen.get(user_id)
    if not ctx:
        await callback.answer("Card session expired.")
        return
    _pending_regen[user_id]["waiting_context"] = True
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore
    await callback.answer()
    await callback.message.reply(ask_for_context(), parse_mode="HTML")  # type: ignore


@word_router.message(_WaitingRegenContext())
async def handle_regen_context(
    message: Message,
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = message.from_user.id  # type: ignore
    ctx = _pending_regen.pop(user_id, None)
    if not ctx or not message.text:
        return

    context = message.text.strip()
    word: str = ctx["word"]
    old_card: VocabCard = ctx["card"]
    deck_name: str | None = ctx.get("deck_name")

    if old_card.backend_id:
        with contextlib.suppress(Exception):
            await agent._anki.delete_card(old_card.backend_id)

    await message.reply(regenerating(word), parse_mode="HTML")

    try:
        card = await agent.capture_word(
            word=word,
            target_lang=ctx["target_lang"],
            native_lang=ctx["native_lang"],
            context=context,
            deck_id=ctx.get("active_deck_id") or None,
        )
    except WordCaptureError:
        await message.reply(word_capture_failed(word), parse_mode="HTML")
        return
    except AppError:
        await message.reply(word_capture_error(), parse_mode="HTML")
        return

    _pending_regen[user_id] = {
        "word": word,
        "card": card,
        "target_lang": ctx["target_lang"],
        "native_lang": ctx["native_lang"],
        "active_deck_id": ctx.get("active_deck_id"),
        "deck_name": deck_name,
    }

    display_word = f"{card.article} {card.word}" if card.article else card.word
    text = (
        card_saved(
            display_word, card.translation, card.example_sentence, card.grammar_note, deck_name
        )
        if card.backend_id
        else card_saved_no_backend(
            display_word, card.translation, card.example_sentence, card.grammar_note, deck_name
        )
    )
    await message.reply(text, parse_mode="HTML", reply_markup=_word_card_keyboard())
