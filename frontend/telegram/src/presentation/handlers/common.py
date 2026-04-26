from enum import StrEnum
from html import escape

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient
from src.presentation import messages

PLATFORM = "telegram"

router = Router(name="common")
catch_all_router = Router(name="catch_all")

logger = structlog.get_logger(__name__)


class CallbackAction(StrEnum):
    """Callback data prefixes for inline keyboard buttons.

    Format: f"{CallbackAction.LESSON}:reading"
    Routed via: F.data.startswith(f"{CallbackAction.LESSON}:")
    """

    LESSON = "lesson"
    DELETE_CARD = "delcard"
    WRITING = "writing"
    WORD_REGEN = "word_regen"
    NEXT_READING = "nread"
    NEXT_LISTENING = "nlisten"
    NEXT_WRITING = "nwrite"
    WRITING_START = "wstart"  # wstart:{theme_id} — start writing with this theme
    WRITING_ANOTHER = "wanother"  # fetch another random theme, edit message in place
    WRITING_CHOOSE = "wchoose"  # expand to full theme list picker


def contact_id(message: Message) -> str:
    """Extract platform user ID from a Telegram message."""
    assert message.from_user is not None, "message.from_user is None — anonymous message?"
    return str(message.from_user.id)


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


@router.message(Command("exit"))
async def cmd_exit(message: Message) -> None:
    # Bot is stateless — no in-memory state to clear.
    # Backend session TTL (15 min) handles expiry naturally.
    await message.answer(messages.session_cancelled())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(messages.help_text(), parse_mode="HTML")


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
