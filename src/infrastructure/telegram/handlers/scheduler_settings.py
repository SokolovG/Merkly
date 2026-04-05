import logging
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.card_backends.anki import AnkiClient
from src.infrastructure.card_backends.mochi import MochiClient
from src.infrastructure.exceptions import CardBackendError
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
from src.infrastructure.telegram.messages import complete_setup

logger = logging.getLogger(__name__)

scheduler_router = Router()

_waiting_time: set[int] = set()
_waiting_deck: dict[int, list[tuple[str, str]]] = {}


def _scheduler_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Disable" if enabled else "✅ Enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="sched:toggle")],
            [InlineKeyboardButton(text="🕐 Set time", callback_data="sched:settime")],
            [InlineKeyboardButton(text="🗂 Pick deck", callback_data="sched:pickdeck")],
        ]
    )


def _deck_keyboard(decks: list[tuple[str, str]], active_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✅ {name}" if backend_id == active_id else name,
                callback_data=f"scheddeck:{i}",
            )
        ]
        for i, (name, backend_id) in enumerate(decks)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _status_text(profile) -> str:
    status = "✅ Enabled" if profile.vocab_scheduler_enabled else "❌ Disabled"
    deck_name = "default deck"
    if profile.vocab_scheduler_deck_id:
        match = next(
            (d for d in profile.decks if d.backend_id == profile.vocab_scheduler_deck_id),
            None,
        )
        deck_name = match.name if match else profile.vocab_scheduler_deck_id
    return (
        f"⏰ <b>Daily Vocab Scheduler</b>\n\n"
        f"Status: {status}\n"
        f"Time: {profile.vocab_scheduler_time} (your local time)\n"
        f"Deck: {deck_name}\n"
        f"Cards per day: {profile.vocab_card_count}"
    )


def _update_profile(profile, **kwargs):
    return profile.__class__(
        **{**{f: getattr(profile, f) for f in profile.__struct_fields__}, **kwargs}
    )


@scheduler_router.message(F.text == "/scheduler")
async def cmd_scheduler(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    if message.from_user is None:
        return
    profile = await profile_repo.get(message.from_user.id)
    if not profile:
        await message.reply(complete_setup())
        return
    await message.reply(
        _status_text(profile),
        parse_mode="HTML",
        reply_markup=_scheduler_keyboard(profile.vocab_scheduler_enabled),
    )


@scheduler_router.callback_query(F.data == "sched:toggle")
async def handle_toggle(
    callback: CallbackQuery,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    updated = _update_profile(profile, vocab_scheduler_enabled=not profile.vocab_scheduler_enabled)
    await profile_repo.save(updated)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _status_text(updated),
            parse_mode="HTML",
            reply_markup=_scheduler_keyboard(updated.vocab_scheduler_enabled),
        )


@scheduler_router.callback_query(F.data == "sched:settime")
async def handle_settime(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    _waiting_time.add(user_id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(
            "Send me the time in <b>HH:MM</b> format (e.g. <b>09:00</b>, <b>21:30</b>)",
            parse_mode="HTML",
        )


@scheduler_router.message(
    lambda msg: msg.from_user is not None and msg.from_user.id in _waiting_time
)
async def handle_time_input(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    if message.from_user is None or not message.text:
        return
    user_id = message.from_user.id
    value = message.text.strip().replace(".", ":")
    if not re.match(r"^\d{1,2}:\d{2}$", value):
        await message.reply("Please use HH:MM format (e.g. <b>09:00</b>)", parse_mode="HTML")
        return
    h, m = value.split(":")
    formatted = f"{int(h):02d}:{m}"
    _waiting_time.discard(user_id)
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        return
    updated = _update_profile(profile, vocab_scheduler_time=formatted)
    await profile_repo.save(updated)
    await message.reply(
        _status_text(updated),
        parse_mode="HTML",
        reply_markup=_scheduler_keyboard(updated.vocab_scheduler_enabled),
    )


@scheduler_router.callback_query(F.data == "sched:pickdeck")
async def handle_pickdeck(
    callback: CallbackQuery,
    card_gateway: FromDishka[AnkiClient | MochiClient],
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    try:
        decks = await card_gateway.list_decks()
    except CardBackendError:
        await callback.answer("Could not fetch decks.")
        return
    if not decks:
        await callback.answer("No decks found. Create one with /newdeck.")
        return
    _waiting_deck[user_id] = decks
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(
            "Choose the deck for daily vocab:",
            reply_markup=_deck_keyboard(decks, profile.vocab_scheduler_deck_id),
        )


@scheduler_router.callback_query(F.data.startswith("scheddeck:"))
async def handle_deck_callback(
    callback: CallbackQuery,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    user_id = callback.from_user.id
    decks = _waiting_deck.get(user_id)
    if not decks:
        await callback.answer("Session expired. Tap 'Pick deck' again.")
        return
    raw = (callback.data or "").split(":", 1)
    if len(raw) < 2 or not raw[1].isdigit():
        await callback.answer("Invalid selection.")
        return
    idx = int(raw[1])
    if idx >= len(decks):
        await callback.answer("Invalid selection.")
        return
    _, backend_id = decks[idx]
    _waiting_deck.pop(user_id, None)
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    updated = _update_profile(profile, vocab_scheduler_deck_id=backend_id)
    await profile_repo.save(updated)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _status_text(updated),
            parse_mode="HTML",
            reply_markup=_scheduler_keyboard(updated.vocab_scheduler_enabled),
        )
