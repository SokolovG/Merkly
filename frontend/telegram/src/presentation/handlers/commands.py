"""Core command handlers — thin I/O layer calling BackendClient.

No _pending_* dicts. Session state lives on backend (Redis).
Answer detection uses GET /sessions/active on every non-command message.
"""

from html import escape

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient, CardDTO
from src.presentation import messages

router = Router()
catch_all_router = Router()

logger = structlog.get_logger(__name__)

_PLATFORM = "telegram"
_CB_DEL_CARD = "delcard"
_CB_WRITING = "writing"


def _contact_id(message: Message) -> str:
    return str(message.from_user.id)  # type: ignore[union-attr]


def _cards_keyboard(cards: list[CardDTO]) -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(
            text=f"🗑 {card.word}",
            callback_data=f"{_CB_DEL_CARD}:{card.word[:20]}",
        )
        for card in cards
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    if len(cards) > 1:
        rows.append(
            [InlineKeyboardButton(text="🗑 Delete all", callback_data=f"{_CB_DEL_CARD}:all")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    contact_id = _contact_id(message)
    identity = await backend.lookup_identity(_PLATFORM, contact_id)
    if identity:
        structlog.contextvars.bind_contextvars(user_id=identity.user_id, contact_id=contact_id)
        logger.info("cmd_start")
        await message.answer(
            "👋 Welcome back! Ready to learn?\n\n/session — reading\n/listen — listening\n/vocab — vocabulary",
            parse_mode="HTML",
        )
    else:
        logger.info("cmd_start_no_profile", contact_id=contact_id)
        await message.answer(
            "👋 Welcome! Your account isn't set up yet.\n\n"
            "Please use the main bot to complete onboarding first.",
        )


@router.message(Command("session"))
async def cmd_session(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    contact_id = _contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=contact_id)
    logger.info("cmd_session")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_reading_session(_PLATFORM, contact_id)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    article_msg = (
        f"📰 <b>{escape(result.title)}</b>\n\n"
        f"{escape(result.content[:1500])}\n\n"
        "---\nAnswer these questions:\n\n"
    )
    for i, q in enumerate(result.questions, 1):
        article_msg += f"<b>{i}.</b> {escape(q)}\n"
    article_msg += f"\nSend your answers as one message (answer all {len(result.questions)})."

    await message.answer(article_msg, parse_mode="HTML")


@router.message(Command("vocab"))
async def cmd_vocab(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    contact_id = _contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=contact_id)

    # Parse args: /vocab | /vocab 5 | /vocab university | /vocab university 5
    text = message.text or ""
    cmd_end = text.find(" ")
    args_str = text[cmd_end:].strip() if cmd_end != -1 else ""

    force_topic: str | None = None
    count: int = 8  # default

    if args_str:
        parts = args_str.split(maxsplit=1)
        if parts[0].isdigit():
            count = int(parts[0])
            force_topic = parts[1].strip() if len(parts) == 2 else None
        else:
            rparts = args_str.rsplit(maxsplit=1)
            if len(rparts) == 2 and rparts[1].isdigit():
                force_topic = rparts[0].strip() or None
                count = int(rparts[1])
            elif args_str.isdigit():
                count = int(args_str)
            else:
                force_topic = args_str

    logger.info("cmd_vocab", force_topic=force_topic, count=count)
    await message.answer(messages.fetching_vocab())

    try:
        result = await backend.generate_vocab(_PLATFORM, contact_id, count, force_topic)
    except Exception as e:
        await message.answer(messages.vocab_failed(str(e)))
        return

    if not result.cards:
        await message.answer(messages.vocab_empty())
        return

    card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in result.cards)
    response = f"{messages.vocab_header(result.topic, len(result.cards))}\n\n{card_list}"
    await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(result.cards))


@router.message(Command("repeat"))
async def cmd_repeat(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    contact_id = _contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=contact_id)
    logger.info("cmd_repeat")

    try:
        result = await backend.get_repeat(_PLATFORM, contact_id)
    except Exception as e:
        await message.answer(messages.vocab_failed(str(e)))
        return

    if not result.cards:
        await message.answer(messages.repeat_empty())
        return

    word_list = "\n".join(
        f"{i}. <b>{escape(c.word)}</b> — {escape(c.translation)}"
        for i, c in enumerate(result.cards, 1)
    )
    await message.answer(
        f"{messages.repeat_header(len(result.cards))}{word_list}", parse_mode="HTML"
    )


@router.message(Command("exit"))
async def cmd_exit(message: Message) -> None:
    # Bot is stateless — no in-memory state to clear.
    # Backend session TTL (15 min) handles expiry naturally.
    await message.answer(messages.session_cancelled())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(messages.help_text(), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Answer handler — replaces _HasPendingSession / _HasPendingWriting
# ---------------------------------------------------------------------------


@router.message(F.text & ~F.text.startswith("/"))
async def handle_answer(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Handle user's answer to an active session question or writing exercise."""
    structlog.contextvars.clear_contextvars()
    contact_id = _contact_id(message)

    try:
        active = await backend.get_active_session(_PLATFORM, contact_id)
    except Exception:
        return  # backend unreachable — silently ignore

    if active.session_id is None:
        return  # no active session — catch_all_router will handle if needed

    if active.state == "questions":
        await message.answer("🔍 Reviewing your answers…")
        try:
            result = await backend.submit_answer(active.session_id, message.text or "")
        except Exception as e:
            await message.answer(f"❌ Couldn't review answers: {e}")
            return

        feedback_msg = f"📝 <b>Feedback:</b>\n\n{escape(result.feedback)}"

        if result.writing_available:
            writing_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✍️ Sentences", callback_data=f"{_CB_WRITING}:sentences"
                        ),
                        InlineKeyboardButton(
                            text="📝 Grammar", callback_data=f"{_CB_WRITING}:grammar"
                        ),
                        InlineKeyboardButton(
                            text="📰 Essay", callback_data=f"{_CB_WRITING}:article"
                        ),
                    ]
                ]
            )
            await message.answer(feedback_msg, parse_mode="HTML", reply_markup=writing_kb)
        else:
            await message.answer(feedback_msg, parse_mode="HTML")

    elif active.state == "writing":
        await message.answer("✍️ Reviewing your writing…")
        try:
            result = await backend.submit_writing(
                active.session_id, message.text or "", "sentences"
            )
        except Exception as e:
            await message.answer(f"❌ Couldn't review writing: {e}")
            return

        response = f"✍️ <b>Writing feedback:</b>\n\n{escape(result.feedback)}"
        if result.cards:
            card_list = "\n".join(
                f"• {escape(c.word)} → {escape(c.translation)}" for c in result.cards
            )
            response += f"\n\n📚 <b>Cards saved ({len(result.cards)}):</b>\n{card_list}"
        await message.answer(response, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Writing exercise mode selection callback
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(f"{_CB_WRITING}:"))
async def handle_writing_start(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    mode = (callback.data or "").split(":", 1)[1]
    contact_id = str(callback.from_user.id)

    try:
        active = await backend.get_active_session(_PLATFORM, contact_id)
    except Exception:
        await callback.answer("Session expired")
        return

    if not active.session_id:
        await callback.answer("Session expired")
        return

    await callback.answer()
    mode_label = {
        "sentences": "✍️ Sentences",
        "grammar": "📝 Grammar focus",
        "article": "📰 Essay",
    }.get(mode, "✍️ Writing exercise")
    await callback.message.answer(  # type: ignore[union-attr]
        f"<b>{mode_label}:</b>\n\nWrite your exercise and send it as one message.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Card delete callback — visual acknowledgement only (backend DELETE is 19-06)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(f"{_CB_DEL_CARD}:"))
async def handle_delete_card(callback: CallbackQuery) -> None:
    action = (callback.data or "").split(":", 1)[1]
    if action == "all":
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
        await callback.answer("🗑 Removed from view")
    else:
        await callback.answer(f"🗑 {action} removed from view")
        # Remove the tapped button from the keyboard
        if callback.message and callback.message.reply_markup:
            old_kb = callback.message.reply_markup.inline_keyboard
            new_rows = [
                [btn for btn in row if not btn.callback_data == callback.data] for row in old_kb
            ]
            new_rows = [row for row in new_rows if row]
            if new_rows:
                await callback.message.edit_reply_markup(
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows)
                )
            else:
                await callback.message.edit_reply_markup(reply_markup=None)


# ---------------------------------------------------------------------------
# Catch-all — must be registered last
# ---------------------------------------------------------------------------


@catch_all_router.message(F.text)
async def handle_unknown(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Reply with help for unrecognized messages that have no active session."""
    if message.text and message.text.startswith("/"):
        return
    contact_id = _contact_id(message)
    try:
        active = await backend.get_active_session(_PLATFORM, contact_id)
        if active.session_id is not None:
            return  # handle_answer will take it; don't double-respond
    except Exception:
        pass
    await message.answer(messages.unknown_message())
