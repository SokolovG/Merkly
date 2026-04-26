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

from src.infrastructure.backend_client import BackendClient
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM, CallbackAction, contact_id

router = Router(name="writing")

logger = structlog.get_logger(__name__)


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


@router.callback_query(F.data.startswith(f"{CallbackAction.WRITING}:"))
async def handle_writing_start(callback: CallbackQuery, backend: FromDishka[BackendClient]) -> None:
    """Writing mode selection callback (sentences / grammar / essay)."""
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
