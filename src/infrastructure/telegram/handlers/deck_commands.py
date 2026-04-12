import logging

import structlog
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.domain.entities import UserDeck
from src.infrastructure.card_backends.anki import AnkiClient
from src.infrastructure.card_backends.mochi import MochiClient
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.exceptions import CardBackendError
from src.infrastructure.telegram.messages import (
    complete_setup,
    deck_backend_error,
    deck_created,
    deck_no_decks,
    deck_pick_active,
    deck_selected,
)

logger = logging.getLogger(__name__)

deck_router = Router()

# Users waiting to type a deck name after bare /newdeck
_pending_newdeck: set[int] = set()
# Pending /setdeck state: user_id → list of (display_name, backend_id)
_pending_setdeck: dict[int, list[tuple[str, str]]] = {}


def _setdeck_keyboard(decks: list[tuple[str, str]], active_deck_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✅ {name}" if backend_id == active_deck_id else name,
                callback_data=f"setdeck:{i}",
            )
        ]
        for i, (name, backend_id) in enumerate(decks)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _create_deck(
    message: Message,
    name: str,
    card_gateway: AnkiClient | MochiClient,
    profile_repo: ProfileRepository,
) -> None:
    if message.from_user is None:
        return
    user_id = message.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
    try:
        backend_id = await card_gateway.create_deck(name)
    except CardBackendError as e:
        await message.reply(deck_backend_error(str(e)), parse_mode="HTML")
        return
    new_deck = UserDeck(name=name, backend_id=backend_id)
    updated_decks = [d for d in profile.decks if d.name != name]
    updated_decks.append(new_deck)
    updated_profile = profile.__class__(
        **{
            **{f: getattr(profile, f) for f in profile.__struct_fields__},
            "decks": updated_decks,
            "active_deck_id": backend_id,
        }
    )
    await profile_repo.save(updated_profile)
    await message.reply(deck_created(name), parse_mode="HTML")


@deck_router.message(F.text.startswith("/newdeck"))
async def handle_newdeck(
    message: Message,
    card_gateway: FromDishka[AnkiClient | MochiClient],
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None:
        return
    user_id = message.from_user.id

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        _pending_newdeck.add(user_id)
        await message.reply("Send me the deck name:", parse_mode="HTML")
        return

    name = parts[1].strip()
    _pending_newdeck.discard(user_id)
    await _create_deck(message, name, card_gateway, profile_repo)


@deck_router.message(lambda msg: msg.from_user is not None and msg.from_user.id in _pending_newdeck)
async def handle_newdeck_name(
    message: Message,
    card_gateway: FromDishka[AnkiClient | MochiClient],
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None or not message.text:
        return
    user_id = message.from_user.id
    name = message.text.strip()
    _pending_newdeck.discard(user_id)
    await _create_deck(message, name, card_gateway, profile_repo)


@deck_router.message(F.text == "/setdeck")
async def handle_setdeck(
    message: Message,
    card_gateway: FromDishka[AnkiClient | MochiClient],
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None:
        return
    user_id = message.from_user.id

    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)

    try:
        decks: list[tuple[str, str]] = await card_gateway.list_decks()
    except CardBackendError as e:
        await message.reply(deck_backend_error(str(e)), parse_mode="HTML")
        return

    if not decks:
        await message.reply(deck_no_decks())
        return

    _pending_setdeck[user_id] = decks
    await message.reply(
        deck_pick_active(), reply_markup=_setdeck_keyboard(decks, profile.active_deck_id)
    )


@deck_router.callback_query(F.data.startswith("setdeck:"))
async def handle_setdeck_callback(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = callback.from_user.id
    decks = _pending_setdeck.get(user_id)
    if not decks:
        await callback.answer("Session expired. Run /setdeck again.")
        return

    raw = (callback.data or "").split(":", 1)
    if len(raw) < 2 or not raw[1].isdigit():
        await callback.answer("Invalid selection.")
        return

    idx = int(raw[1])
    if idx >= len(decks):
        await callback.answer("Invalid selection.")
        return

    display_name, backend_id = decks[idx]
    _pending_setdeck.pop(user_id, None)

    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
    updated_profile = profile.__class__(
        **{
            **{f: getattr(profile, f) for f in profile.__struct_fields__},
            "active_deck_id": backend_id,
        }
    )
    await profile_repo.save(updated_profile)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(deck_selected(display_name), parse_mode="HTML")
