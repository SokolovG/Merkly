"""+word capture handler — thin I/O, calls BackendClient.

Regen flow uses aiogram FSMContext for one piece of state: the word string
while waiting for context input. No full card data stored bot-side.
"""

from html import escape

import structlog
from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient, CaptureWordResponse
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM, CallbackAction
from src.presentation.handlers.common import contact_id as get_contact_id

router = Router()
logger = structlog.get_logger(__name__)


class RegenState(StatesGroup):
    waiting_for_context = State()


class _PlusWordFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.text and message.text.startswith("+") and len(message.text) > 1)


def _word_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Wrong meaning?", callback_data=CallbackAction.WORD_REGEN
                ),
            ]
        ]
    )


def _format_card(result: CaptureWordResponse) -> str:
    c = result.card
    lines = [f"📥 <b>{escape(c.word)}</b> — {escape(c.translation)}"]
    if c.article:
        lines[0] = f"📥 <b>{escape(c.article)} {escape(c.word)}</b> — {escape(c.translation)}"
    if c.grammar_note:
        lines.append(f"<i>{escape(c.grammar_note)}</i>")
    if c.example_sentence:
        lines.append(f"💬 {escape(c.example_sentence)}")
    return "\n".join(lines)


@router.message(_PlusWordFilter())
async def cmd_capture_word(
    message: Message,
    state: FSMContext,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    cid = get_contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)

    raw = (message.text or "")[1:]
    if "/" in raw:
        word, context = raw.split("/", 1)
        word = word.strip()
        context = context.strip() or None
    else:
        word = raw.strip()
        context = None

    if not word:
        await message.answer("❓ Send a word after +, e.g. +Brot")
        return

    logger.info("cmd_capture_word", word=word, has_context=context is not None)

    # T31: send status message immediately; delete it once response is ready
    status_msg = await message.answer("🔍 Looking up…")

    try:
        result = await backend.capture_word(PLATFORM, cid, word, context)
    except Exception as e:
        await message.answer(f"❌ Couldn't capture word: {e}")
        try:
            await status_msg.delete()
        except Exception:
            pass
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    # T30: duplicate — show notice, skip card display and FSM state
    if result.already_exists:
        await message.answer(messages.word_already_exists(word), parse_mode="HTML")
        return

    # Store word + card ID for potential regen — old card deleted on regeneration
    await state.update_data(regen_word=word, regen_card_id=result.pool_card_id)

    await message.answer(_format_card(result), parse_mode="HTML", reply_markup=_word_keyboard())


@router.callback_query(F.data == CallbackAction.WORD_REGEN)
async def handle_wrong_meaning(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegenState.waiting_for_context)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Send context for the word (e.g. <i>slang</i>, <i>food</i>, a phrase).\n"
            "I'll regenerate the card with the correct meaning.",
            parse_mode="HTML",
        )


@router.message(RegenState.waiting_for_context, F.text)
async def handle_regen_context(
    message: Message,
    state: FSMContext,
    backend: FromDishka[BackendClient],
) -> None:
    data = await state.get_data()
    word = data.get("regen_word", "")
    old_card_id: str | None = data.get("regen_card_id") or None
    context = message.text or ""
    cid = get_contact_id(message)

    await state.clear()

    if not word:
        await message.answer("❓ Lost track of the word. Try +word again.")
        return

    logger.info("cmd_regen_word", word=word)
    try:
        result = await backend.regenerate_word(PLATFORM, cid, word, context, old_card_id)
    except Exception as e:
        await message.answer(f"❌ Couldn't regenerate card: {e}")
        return

    await message.answer(
        f"♻️ Regenerated:\n\n{_format_card(result)}",
        parse_mode="HTML",
    )
