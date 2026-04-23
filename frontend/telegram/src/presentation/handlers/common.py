"""Shared constants and helpers for all Telegram handlers."""

from enum import StrEnum

from aiogram.types import Message

PLATFORM = "telegram"


class CallbackAction(StrEnum):
    """Callback data prefixes for inline keyboard buttons.

    Format: f"{CallbackAction.LESSON}:reading"
    Routed via: F.data.startswith(f"{CallbackAction.LESSON}:")
    """

    LESSON = "lesson"
    DELETE_CARD = "delcard"
    WRITING = "writing"
    WORD_OK = "word_ok"
    WORD_REGEN = "word_regen"


def contact_id(message: Message) -> str:
    """Extract platform user ID from a Telegram message."""
    assert message.from_user is not None, "message.from_user is None — anonymous message?"
    return str(message.from_user.id)
