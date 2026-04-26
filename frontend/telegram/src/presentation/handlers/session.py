from html import escape

import structlog
from aiogram import F, Router
from aiogram.filters import Command
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

router = Router(name="session")

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
    if result.session_type == "listening":
        show_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📄 Show transcript",
                        callback_data=f"{CallbackAction.SHOW_TRANSCRIPT}:{result.session_id}",
                    )
                ]
            ]
        )
    await target.answer(header, parse_mode="HTML", reply_markup=show_kb if show_kb else None)


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
            next_btn = (
                InlineKeyboardButton(
                    text="🎧 Another audio",
                    callback_data=str(CallbackAction.NEXT_LISTENING),
                )
                if result.session_type == "listening"
                else InlineKeyboardButton(
                    text="📖 Another article",
                    callback_data=str(CallbackAction.NEXT_READING),
                )
            )
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
                    [next_btn],
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


@router.callback_query(F.data.startswith(f"{CallbackAction.LESSON}:"))
async def handle_lesson_choice(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    choice = (callback.data or "").split(":", 1)[1]
    cid = str(callback.from_user.id)

    await callback.answer()
    if not isinstance(callback.message, Message):
        return
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


@router.callback_query(F.data.startswith(f"{CallbackAction.SHOW_TRANSCRIPT}:"))
async def handle_show_transcript(
    callback: CallbackQuery, backend: FromDishka[BackendClient]
) -> None:
    session_id = (callback.data or "").split(":", 1)[1]

    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    try:
        transcript = await backend.get_session_transcript(session_id)
    except Exception:
        await callback.answer("Session expired — transcript no longer available.", show_alert=True)
        return

    transcript_msg = await callback.message.answer(
        f"📄 <b>Transcript:</b>\n\n{escape(transcript)}", parse_mode="HTML"
    )

    hide_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙈 Hide transcript",
                    callback_data=f"{CallbackAction.HIDE_TRANSCRIPT}:{session_id}:{transcript_msg.message_id}",
                )
            ]
        ]
    )

    await callback.message.edit_reply_markup(reply_markup=hide_kb)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CallbackAction.HIDE_TRANSCRIPT}:"))
async def handle_hide_transcript(callback: CallbackQuery) -> None:
    # callback_data format: HIDE_TRANSCRIPT:{session_id}:{transcript_message_id}
    parts = (callback.data or "").split(":")
    session_id = parts[1] if len(parts) > 1 else ""
    transcript_msg_id = int(parts[2]) if len(parts) > 2 else None

    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    if transcript_msg_id is not None:
        try:
            await callback.message.bot.delete_message(  # ty: ignore
                chat_id=callback.message.chat.id,
                message_id=transcript_msg_id,
            )
        except Exception:
            pass  # already deleted or inaccessible

    show_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Show transcript",
                    callback_data=f"{CallbackAction.SHOW_TRANSCRIPT}:{session_id}",
                )
            ]
        ]
    )

    await callback.message.edit_reply_markup(reply_markup=show_kb)
    await callback.answer()
