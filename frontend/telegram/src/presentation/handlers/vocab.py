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

from src.infrastructure.backend_client import BackendClient, CardDTO
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM, CallbackAction, contact_id

router = Router(name="vocab")

logger = structlog.get_logger(__name__)


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


@router.message(Command("vocab"))
async def cmd_vocab(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)

    text = message.text or ""
    cmd_end = text.find(" ")
    args_str = text[cmd_end:].strip() if cmd_end != -1 else ""

    force_topic: str | None = None
    count: int = 8

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
