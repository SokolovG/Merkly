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

from src.infrastructure.backend_client import BackendClient, CardDTO, StartSessionResponse
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM, CallbackAction, contact_id

router = Router()
catch_all_router = Router()

logger = structlog.get_logger(__name__)


def _lesson_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Reading",
                    callback_data=f"{CallbackAction.LESSON}:reading",
                ),
                InlineKeyboardButton(
                    text="🎧 Listening",
                    callback_data=f"{CallbackAction.LESSON}:listening",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🃏 Vocab",
                    callback_data=f"{CallbackAction.LESSON}:vocab",
                ),
            ],
        ]
    )


def _cards_keyboard(cards: list[CardDTO]) -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(
            text=f"🗑 {card.word}",
            callback_data=f"{CallbackAction.DELETE_CARD}:{card.word[:20]}",
        )
        for card in cards
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    if len(cards) > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Delete all",
                    callback_data=f"{CallbackAction.DELETE_CARD}:all",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _next_session_keyboard(session_type: str | None = None) -> InlineKeyboardMarkup:
    """Inline keyboard shown after session feedback to start another session."""
    buttons = []
    if session_type != "listening":
        buttons.append(
            InlineKeyboardButton(
                text="📖 Another article",
                callback_data=str(CallbackAction.NEXT_READING),
            )
        )
    if session_type != "reading":
        buttons.append(
            InlineKeyboardButton(
                text="🎧 Another audio",
                callback_data=str(CallbackAction.NEXT_LISTENING),
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text="✍️ New writing task",
            callback_data=str(CallbackAction.NEXT_WRITING),
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _random_theme_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown alongside a single random writing theme."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Start", callback_data=f"{CallbackAction.WRITING_START}:__id__"
                ),
                InlineKeyboardButton(
                    text="🎲 Another", callback_data=str(CallbackAction.WRITING_ANOTHER)
                ),
                InlineKeyboardButton(
                    text="📋 Choose", callback_data=str(CallbackAction.WRITING_CHOOSE)
                ),
            ]
        ]
    )


def _random_theme_keyboard_with_id(theme_id: str) -> InlineKeyboardMarkup:
    """Random-theme keyboard with the real theme_id baked into the Start button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Start",
                    callback_data=f"{CallbackAction.WRITING_START}:{theme_id}",
                ),
                InlineKeyboardButton(
                    text="🎲 Another",
                    callback_data=str(CallbackAction.WRITING_ANOTHER),
                ),
                InlineKeyboardButton(
                    text="📋 Choose",
                    callback_data=str(CallbackAction.WRITING_CHOOSE),
                ),
            ]
        ]
    )


def _theme_list_keyboard(themes: list) -> InlineKeyboardMarkup:
    """One button per theme in the picker list. callback = wstart:{theme_id}"""
    rows = [
        [
            InlineKeyboardButton(
                text=t.theme[:60],
                callback_data=f"{CallbackAction.WRITING_START}:{t.id}",
            )
        ]
        for t in themes
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _send_session_result(target: Message, result: StartSessionResponse) -> None:
    """Format and send a session start result (reading or listening)."""
    if result.session_type == "reading":
        header = (
            f"📰 <b>{escape(result.title)}</b>\n\n"
            f"{escape(result.content[:1500])}\n\n---\nAnswer these questions:\n\n"
        )
    else:
        audio_line = (
            f'\n\n<a href="{escape(result.audio_url)}">▶️ Listen to episode</a>'
            if result.audio_url
            else ""
        )
        header = f"🎧 <b>{escape(result.title)}</b>{audio_line}\n\n"

    for i, q in enumerate(result.questions, 1):
        header += f"<b>{i}.</b> {escape(q)}\n"
    header += f"\nSend your answers as one message (answer all {len(result.questions)})."
    await target.answer(header, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    identity = await backend.lookup_identity(PLATFORM, cid)
    if identity:
        structlog.contextvars.bind_contextvars(user_id=identity.user_id, contact_id=cid)
        logger.info("cmd_start")
        await message.answer(
            "👋 Welcome back! Ready to learn?\n\n/session — reading\n/listen — listening\n/vocab — vocabulary",
            parse_mode="HTML",
        )
    else:
        logger.info("cmd_start_no_profile", contact_id=cid)
        await message.answer(
            "👋 Welcome! Your account isn't set up yet.\n\n"
            "Please use the main bot to complete onboarding first.",
        )


@router.message(Command("session"))
async def cmd_session(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Auto-picks activity from profile learning strategy."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_session")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_session(PLATFORM, cid)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    await _send_session_result(message, result)


@router.message(Command("lesson"))
async def cmd_lesson(message: Message) -> None:
    """Manual activity picker — choose reading, listening, or vocab."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_lesson")

    await message.answer(messages.lesson_picker(), reply_markup=_lesson_keyboard())


@router.message(Command("vocab"))
async def cmd_vocab(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)

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
        result = await backend.generate_vocab(PLATFORM, cid, count, force_topic)
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
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_repeat")

    try:
        result = await backend.get_repeat(PLATFORM, cid)
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


@router.message(Command("reading"))
async def cmd_reading(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Start a reading session directly."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_reading")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_reading_session(PLATFORM, cid)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    await _send_session_result(message, result)


@router.message(Command("listen"))
async def cmd_listen(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Start a listening session directly."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_listen")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_listening_session(PLATFORM, cid)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        logger.warning(e)
        return

    await _send_session_result(message, result)


@router.message(Command("writing"))
async def cmd_writing(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Standalone writing: show one random theme with Start / Another / Choose buttons."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_writing")

    try:
        result = await backend.get_writing_themes(PLATFORM, cid, count=1)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    if not result.themes:
        await message.answer("❌ No writing themes available. Try again later.")
        return

    t = result.themes[0]
    await message.answer(
        f"✍️ <b>Writing topic:</b>\n\n{escape(t.theme)}",
        parse_mode="HTML",
        reply_markup=_random_theme_keyboard_with_id(t.id),
    )


@router.message(Command("next"))
async def cmd_next(message: Message, backend: FromDishka[BackendClient]) -> None:
    """Skip the current session step and start a new session (same type)."""
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_next")

    try:
        active = await backend.get_active_session(PLATFORM, cid)
    except Exception:
        active = None

    # Determine session type to repeat, fall back to auto-pick
    session_type = active.state if active and active.session_id else None

    await message.answer(messages.preparing_lesson())
    try:
        if session_type == "listening":
            result = await backend.start_listening_session(PLATFORM, cid)
        elif session_type in ("questions", "writing", "reading"):
            result = await backend.start_reading_session(PLATFORM, cid)
        else:
            result = await backend.start_session(PLATFORM, cid)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    await _send_session_result(message, result)


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
    cid = contact_id(message)

    try:
        active = await backend.get_active_session(PLATFORM, cid)
    except Exception:
        await message.answer(messages.unknown_message())
        return

    if active.session_id is None or active.state not in ("questions", "writing"):
        await message.answer(messages.unknown_message())
        return

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
                            text="✍️ Sentences",
                            callback_data=f"{CallbackAction.WRITING}:sentences",
                        ),
                        InlineKeyboardButton(
                            text="📝 Grammar",
                            callback_data=f"{CallbackAction.WRITING}:grammar",
                        ),
                        InlineKeyboardButton(
                            text="📰 Essay",
                            callback_data=f"{CallbackAction.WRITING}:article",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="📖 Another article",
                            callback_data=str(CallbackAction.NEXT_READING),
                        ),
                        InlineKeyboardButton(
                            text="🎧 Another audio",
                            callback_data=str(CallbackAction.NEXT_LISTENING),
                        ),
                    ],
                ]
            )
            await message.answer(feedback_msg, parse_mode="HTML", reply_markup=writing_kb)
        else:
            await message.answer(
                feedback_msg,
                parse_mode="HTML",
                reply_markup=_next_session_keyboard(),
            )

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
        await message.answer(
            response,
            parse_mode="HTML",
            reply_markup=_next_session_keyboard(),
        )


# ---------------------------------------------------------------------------
# /lesson picker callback
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(f"{CallbackAction.LESSON}:"))
async def handle_lesson_choice(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    choice = (callback.data or "").split(":", 1)[1]
    cid = str(callback.from_user.id)

    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    # Remove picker keyboard
    await callback.message.edit_reply_markup(reply_markup=None)

    if choice == "vocab":
        await callback.message.answer(messages.fetching_vocab())
        try:
            result = await backend.generate_vocab(PLATFORM, cid, 8)
        except Exception as e:
            await callback.message.answer(messages.vocab_failed(str(e)))
            return
        if not result.cards:
            await callback.message.answer(messages.vocab_empty())
            return
        card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in result.cards)
        response = f"{messages.vocab_header(result.topic, len(result.cards))}\n\n{card_list}"
        await callback.message.answer(
            response, parse_mode="HTML", reply_markup=_cards_keyboard(result.cards)
        )
        return

    await callback.message.answer(messages.preparing_lesson())
    try:
        if choice == "reading":
            result = await backend.start_reading_session(PLATFORM, cid)
        else:  # listening
            result = await backend.start_listening_session(PLATFORM, cid)
    except Exception as e:
        await callback.message.answer(messages.lesson_failed(str(e)))
        return

    await _send_session_result(callback.message, result)


# ---------------------------------------------------------------------------
# "Another article / audio / writing" callbacks
# ---------------------------------------------------------------------------


@router.callback_query(F.data == str(CallbackAction.NEXT_READING))
async def handle_next_reading(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    cid = str(callback.from_user.id)
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_reading_session(PLATFORM, cid)
    except Exception as e:
        await callback.message.answer(messages.lesson_failed(str(e)))
        return
    await _send_session_result(callback.message, result)


@router.callback_query(F.data == str(CallbackAction.NEXT_LISTENING))
async def handle_next_listening(
    callback: CallbackQuery, backend: FromDishka[BackendClient]
) -> None:
    cid = str(callback.from_user.id)
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_listening_session(PLATFORM, cid)
    except Exception as e:
        await callback.message.answer(messages.lesson_failed(str(e)))
        return
    await _send_session_result(callback.message, result)


@router.callback_query(F.data == str(CallbackAction.NEXT_WRITING))
async def handle_next_writing(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    """After-session 'New writing task' button — same as /writing."""
    cid = str(callback.from_user.id)
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    try:
        result = await backend.get_writing_themes(PLATFORM, cid, count=1)
    except Exception as e:
        await callback.message.answer(messages.lesson_failed(str(e)))
        return
    if not result.themes:
        await callback.message.answer("❌ No writing themes available. Try again later.")
        return
    t = result.themes[0]
    await callback.message.answer(
        f"✍️ <b>Writing topic:</b>\n\n{escape(t.theme)}",
        parse_mode="HTML",
        reply_markup=_random_theme_keyboard_with_id(t.id),
    )


@router.callback_query(F.data == str(CallbackAction.WRITING_ANOTHER))
async def handle_writing_another(
    callback: CallbackQuery, backend: FromDishka[BackendClient]
) -> None:
    """🎲 Another — fetch a new random theme and edit the current message."""
    cid = str(callback.from_user.id)
    try:
        result = await backend.get_writing_themes(PLATFORM, cid, count=1)
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)
        return
    if not result.themes:
        await callback.answer("No more themes available.", show_alert=True)
        return
    t = result.themes[0]
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_text(
        f"✍️ <b>Writing topic:</b>\n\n{escape(t.theme)}",
        parse_mode="HTML",
        reply_markup=_random_theme_keyboard_with_id(t.id),
    )


@router.callback_query(F.data == str(CallbackAction.WRITING_CHOOSE))
async def handle_writing_choose(
    callback: CallbackQuery, backend: FromDishka[BackendClient]
) -> None:
    """📋 Choose — expand to full theme list picker."""
    cid = str(callback.from_user.id)
    try:
        result = await backend.get_writing_themes(PLATFORM, cid, count=5)
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)
        return
    if not result.themes:
        await callback.answer("No themes available.", show_alert=True)
        return
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_text(
        "✍️ <b>Choose a writing topic:</b>",
        parse_mode="HTML",
        reply_markup=_theme_list_keyboard(result.themes),
    )


@router.callback_query(F.data.startswith(f"{CallbackAction.WRITING_START}:"))
async def handle_writing_start_theme(
    callback: CallbackQuery, backend: FromDishka[BackendClient]
) -> None:
    """✍️ Start — generate task for the selected theme_id."""
    theme_id = (callback.data or "").split(":", 1)[1]
    cid = str(callback.from_user.id)

    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✍️ Generating your writing task…")
    try:
        result = await backend.start_writing_session(PLATFORM, cid, theme_id)
    except Exception as e:
        await callback.message.answer(messages.lesson_failed(str(e)))
        return
    await callback.message.answer(
        f"✍️ <b>Writing task — {escape(result.theme)}:</b>\n\n{escape(result.task)}\n\n"
        "Write your response and send it as one message.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Writing exercise mode selection callback
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(f"{CallbackAction.WRITING}:"))
async def handle_writing_start(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    mode = (callback.data or "").split(":", 1)[1]
    cid = str(callback.from_user.id)

    try:
        active = await backend.get_active_session(PLATFORM, cid)
    except Exception:
        await callback.answer("Session expired")
        return

    if not active.session_id:
        await callback.answer("Session expired")
        return

    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    mode_label = {
        "sentences": "✍️ Sentences",
        "grammar": "📝 Grammar focus",
        "article": "📰 Essay",
    }.get(mode, "✍️ Writing exercise")
    await callback.message.answer(
        f"<b>{mode_label}:</b>\n\nWrite your exercise and send it as one message.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Card delete callback — visual acknowledgement only (backend DELETE is 19-06)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(f"{CallbackAction.DELETE_CARD}:"))
async def handle_delete_card(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return
    action = (callback.data or "").split(":", 1)[1]
    if action == "all":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("🗑 Removed from view")
    else:
        await callback.answer(f"🗑 {action} removed from view")
        # Remove the tapped button from the keyboard
        if callback.message.reply_markup:
            old_kb = callback.message.reply_markup.inline_keyboard
            new_rows = [
                [btn for btn in row if btn.callback_data != callback.data] for row in old_kb
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
        cmd = message.text.split()[0]
        await message.answer(
            f"❓ Unknown command: <code>{escape(cmd)}</code>\n\nSee /help", parse_mode="HTML"
        )
        return
    cid = contact_id(message)
    try:
        active = await backend.get_active_session(PLATFORM, cid)
        if active.session_id is not None:
            return  # handle_answer will take it; don't double-respond
    except Exception:
        pass
    await message.answer(messages.unknown_message())
