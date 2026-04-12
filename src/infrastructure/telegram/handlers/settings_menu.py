import asyncio
import logging
import re

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.application.vocab_refill_service import VocabRefillService
from src.domain.constants import EPISODE_DURATION_OPTIONS, LANGUAGE_FLAGS
from src.domain.enums import ActivityType, Goal, Language, Level
from src.infrastructure.card_backends.anki import AnkiClient
from src.infrastructure.card_backends.mochi import MochiClient
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from src.infrastructure.exceptions import CardBackendError
from src.infrastructure.telegram.messages import complete_setup

logger = logging.getLogger(__name__)

settings_router = Router()

# user_id → (field, return_submenu)
_editing: dict[int, tuple[str, str]] = {}
# user_id → [(name, backend_id)] from last list_decks() call
_waiting_deck: dict[int, list[tuple[str, str]]] = {}

_ACTIVITY_LABELS = {
    ActivityType.READING: "📖 Reading",
    ActivityType.WRITING: "✍️ Writing",
    ActivityType.LISTENING: "🎧 Listening",
    ActivityType.VOCAB: "📚 Vocab",
}

# Which submenu to return to after editing a field
_FIELD_SUBMENU = {
    "target_lang": "profile",
    "level": "profile",
    "goal": "profile",
    "native_lang": "profile",
    "vocab_card_count": "session",
    "question_count": "session",
    "episode_duration_min": "session",
    "reminder_time": "schedule",
    "utc_offset": "schedule",
    "vocab_scheduler_time": "schedule",
}

# Which submenu to return to after toggling
_TOGGLE_SUBMENU = {
    "reminder_enabled": "schedule",
    "vocab_scheduler_enabled": "schedule",
}


def _lang_label(code: str) -> str:
    return f"{LANGUAGE_FLAGS.get(str(code), '')} {str(code).upper()}"


# ── Text builders ────────────────────────────────────────────────────────────


def _main_text(profile) -> str:
    strategy_parts = "  ·  ".join(
        f"{label.split()[1]} {'✅' if a in profile.learning_strategy else '☐'}"
        for a, label in _ACTIVITY_LABELS.items()
    )
    return (
        "⚙️ <b>Settings</b>\n\n"
        f"<b>Language</b>   {_lang_label(profile.target_lang)}  ·  {profile.level}  ·  {profile.goal}\n"  # noqa
        f"<b>Strategy</b>   {strategy_parts}"
    )


def _profile_text(profile) -> str:
    return (
        "👤 <b>Profile</b>\n\n"
        f"🌍 Language: {_lang_label(profile.target_lang)}\n"
        f"📊 Level: {profile.level}\n"
        f"🎯 Goal: {profile.goal}\n"
        f"🗣 Native: {_lang_label(profile.native_lang)}\n\n"
        "Tap a field to edit:"
    )


def _schedule_text(profile) -> str:
    reminder_str = "❌ Off"
    if profile.reminder_enabled:
        sign = "+" if profile.utc_offset >= 0 else ""
        reminder_str = f"✅ {profile.reminder_time} (UTC{sign}{profile.utc_offset})"

    sched_str = "❌ Off"
    if profile.vocab_scheduler_enabled:
        deck_name = "default deck"
        if profile.vocab_scheduler_deck_id:
            match = next(
                (d for d in profile.decks if d.backend_id == profile.vocab_scheduler_deck_id),
                None,
            )
            deck_name = match.name if match else profile.vocab_scheduler_deck_id
        sched_str = f"✅ {profile.vocab_scheduler_time} → {deck_name}"

    return (
        "🔔 <b>Reminders & Schedule</b>\n\n"
        f"Reminder: {reminder_str}\n"
        f"⏰ Reminder time: {profile.reminder_time}\n"
        f"🌐 UTC offset: {profile.utc_offset:+}\n"
        f"📅 Vocab scheduler: {sched_str}\n\n"
        "Tap a field to edit:"
    )


def _strategy_text(profile) -> str:
    lines = "\n".join(
        f"{label}: {'✅ ON' if a in profile.learning_strategy else '☐ OFF'}"
        for a, label in _ACTIVITY_LABELS.items()
    )
    return f"📋 <b>Strategy</b>\n\n{lines}\n\nTap to toggle:"


def _session_text(profile) -> str:
    return (
        "📊 <b>Session</b>\n\n"
        f"🃏 Vocab cards: {profile.vocab_card_count}\n"
        f"❓ Questions: {profile.question_count}\n"
        f"🎧 Listening clip: {profile.episode_duration_min} min\n\n"
        "Tap a field to edit:"
    )


# ── Keyboard builders ────────────────────────────────────────────────────────


def _main_keyboard(_profile) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profile", callback_data="settings:profile")],
            [InlineKeyboardButton(text="📊 Session", callback_data="settings:session")],
            [
                InlineKeyboardButton(
                    text="🔔 Reminders & Schedule", callback_data="settings:schedule"
                )
            ],
            [InlineKeyboardButton(text="📋 Strategy", callback_data="settings:strategy")],
        ]
    )


def _session_keyboard(profile) -> InlineKeyboardMarkup:
    duration_options = [
        InlineKeyboardButton(
            text=f"{'✅ ' if profile.episode_duration_min == n else ''}{n} min",
            callback_data=f"setpick:episode_duration_min:{n}",
        )
        for n in EPISODE_DURATION_OPTIONS
    ]
    question_options = [
        InlineKeyboardButton(
            text=f"{'✅ ' if profile.question_count == n else ''}{n} questions",
            callback_data=f"setpick:question_count:{n}",
        )
        for n in (2, 3, 5)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🃏 Cards: {profile.vocab_card_count}",
                    callback_data="set:vocab_card_count",
                ),
            ],
            question_options,
            duration_options,
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _profile_keyboard(profile) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🌍 Language: {profile.target_lang}", callback_data="set:target_lang"
                )
            ],
            [InlineKeyboardButton(text=f"📊 Level: {profile.level}", callback_data="set:level")],
            [InlineKeyboardButton(text=f"🎯 Goal: {profile.goal}", callback_data="set:goal")],
            [
                InlineKeyboardButton(
                    text=f"🗣 Native: {profile.native_lang}", callback_data="set:native_lang"
                )
            ],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _schedule_keyboard(profile) -> InlineKeyboardMarkup:
    reminder_label = "🔔 Reminder: ✅ ON" if profile.reminder_enabled else "🔔 Reminder: ❌ OFF"
    sched_label = (
        "📅 Vocab scheduler: ✅ ON"
        if profile.vocab_scheduler_enabled
        else "📅 Vocab scheduler: ❌ OFF"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=reminder_label, callback_data="settoggle:reminder_enabled")],
            [
                InlineKeyboardButton(
                    text=f"⏰ Reminder time: {profile.reminder_time}",
                    callback_data="set:reminder_time",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🌐 UTC: {profile.utc_offset:+}", callback_data="set:utc_offset"
                )
            ],
            [
                InlineKeyboardButton(
                    text=sched_label, callback_data="settoggle:vocab_scheduler_enabled"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⏰ Scheduler time: {profile.vocab_scheduler_time}",
                    callback_data="set:vocab_scheduler_time",
                )
            ],
            [InlineKeyboardButton(text="🗂 Scheduler deck", callback_data="sched:pickdeck")],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _strategy_keyboard(profile) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[
                [
                    InlineKeyboardButton(
                        text=f"{label}: {'✅ ON' if a in profile.learning_strategy else '☐ OFF'}",
                        callback_data=f"settoggle:strategy_{a.value}",
                    )
                ]
                for a, label in _ACTIVITY_LABELS.items()
            ],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _submenu_content(submenu: str, profile) -> tuple:
    if submenu == "profile":
        return _profile_text(profile), _profile_keyboard(profile)
    if submenu == "session":
        return _session_text(profile), _session_keyboard(profile)
    if submenu == "schedule":
        return _schedule_text(profile), _schedule_keyboard(profile)
    if submenu == "strategy":
        return _strategy_text(profile), _strategy_keyboard(profile)
    return _main_text(profile), _main_keyboard(profile)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _update_profile(profile, **kwargs):
    return profile.__class__(
        **{**{f: getattr(profile, f) for f in profile.__struct_fields__}, **kwargs}
    )


_FIELD_PROMPTS: dict[str, str] = {
    "target_lang": "Language to learn — enter a code:\n<code>de  en  es  fr  it  pt</code>",
    "level": (
        "Your level — enter one:\n<code>A1  A2  B1  B2  C1</code>\n"
        "or custom (e.g. <code>B1+</code>)"
    ),
    "goal": "Your goal — enter one:\n<code>travel  work  conversation  general  study</code>",
    "native_lang": (
        "Native language — enter a code:\n<code>de  en  es  fr  it  pt  ru  uk</code>\n"
        "or a name (e.g. <code>Turkish</code>)"
    ),
    "reminder_time": "Reminder time — enter <b>HH:MM</b> (e.g. <b>09:00</b>):",
    "utc_offset": "UTC offset — enter a number (e.g. <code>3</code>, <code>-5</code>):",
    "vocab_scheduler_time": "Vocab scheduler time — enter <b>HH:MM</b> (e.g. <b>09:00</b>):",
    "vocab_card_count": "Vocab cards per session — enter a number (1–20):",
}


def _parse_value(field: str, raw: str):
    """Returns (parsed_value, error_message | None)."""
    value = raw.strip()
    if field == "target_lang":
        try:
            return Language(value.lower()), None
        except ValueError:
            return None, "Unknown code. Use: <code>de en es fr it pt</code>"
    if field == "native_lang":
        val = value.lower()[:20]
        try:
            return Language(val), None
        except ValueError:
            return val, None
    if field == "level":
        normalized = value.upper().replace(" ", "")
        try:
            return Level(normalized), None
        except ValueError:
            return normalized, None  # accept custom levels like "B1+"
    if field == "goal":
        try:
            return Goal(value.lower()), None
        except ValueError:
            return None, "Unknown goal. Use: <code>travel work conversation general study</code>"
    if field in ("reminder_time", "vocab_scheduler_time"):
        value = value.replace(".", ":")
        if not re.match(r"^\d{1,2}:\d{2}$", value):
            return None, "Use <b>HH:MM</b> format, e.g. <b>09:00</b>"
        h, m = value.split(":")
        return f"{int(h):02d}:{m}", None
    if field == "utc_offset":
        try:
            n = int(value.replace("+", ""))
            if not -12 <= n <= 14:
                raise ValueError
            return n, None
        except ValueError:
            return None, "Enter a number between -12 and 14."
    if field == "vocab_card_count":
        try:
            n = int(value)
            if not 1 <= n <= 20:
                raise ValueError
            return n, None
        except ValueError:
            return None, "Enter a number between 1 and 20."
    return None, "Unknown field."


# ── Handlers ─────────────────────────────────────────────────────────────────


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message, profile_repo: FromDishka[ProfileRepository]) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None:
        return
    profile = await profile_repo.get(message.from_user.id)
    if not profile:
        await message.reply(complete_setup())
        return

    structlog.contextvars.bind_contextvars(
        user_id=str(profile.id), telegram_id=message.from_user.id
    )
    await message.reply(
        _main_text(profile),
        parse_mode="HTML",
        reply_markup=_main_keyboard(profile),
    )


@settings_router.callback_query(F.data.startswith("settings:"))
async def handle_nav(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    submenu = (callback.data or "").split(":", 1)[1]
    profile = await profile_repo.get(callback.from_user.id)
    if not profile:
        await callback.answer("Profile not found.")
        return

    structlog.contextvars.bind_contextvars(
        user_id=str(profile.id), telegram_id=callback.from_user.id
    )
    text, keyboard = _submenu_content(submenu, profile)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@settings_router.callback_query(F.data.startswith("set:"))
async def handle_edit_button(callback: CallbackQuery) -> None:
    field = (callback.data or "").split(":", 1)[1]
    if field not in _FIELD_PROMPTS:
        await callback.answer("Unknown field.")
        return
    submenu = _FIELD_SUBMENU.get(field, "main")
    _editing[callback.from_user.id] = (field, submenu)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(_FIELD_PROMPTS[field], parse_mode="HTML")


@settings_router.callback_query(F.data.startswith("setpick:"))
async def handle_pick(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    # setpick:{field}:{value}
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        await callback.answer("Invalid.")
        return
    _, field, raw_value = parts
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
    try:
        value = int(raw_value)
    except ValueError:
        await callback.answer("Invalid value.")
        return
    updated = _update_profile(profile, **{field: value})
    await profile_repo.save(updated)
    await callback.answer(f"✅ Set to {value}")
    submenu = _FIELD_SUBMENU.get(field, "main")
    text, keyboard = _submenu_content(submenu, updated)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@settings_router.callback_query(F.data.startswith("settoggle:"))
async def handle_toggle(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    field = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)

    if field.startswith("strategy_"):
        activity_value = field[len("strategy_") :]
        try:
            activity = ActivityType(activity_value)
        except ValueError:
            await callback.answer("Unknown activity.")
            return
        strategy = list(profile.learning_strategy)
        if activity in strategy:
            if len(strategy) <= 1:
                await callback.answer("Keep at least one activity enabled.")
                return
            strategy.remove(activity)
        else:
            strategy.append(activity)
        updated = _update_profile(profile, learning_strategy=strategy)
        return_submenu = "strategy"
    else:
        updated = _update_profile(profile, **{field: not getattr(profile, field)})
        return_submenu = _TOGGLE_SUBMENU.get(field, "main")

    await profile_repo.save(updated)
    await callback.answer()
    text, keyboard = _submenu_content(return_submenu, updated)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@settings_router.callback_query(F.data == "sched:pickdeck")
async def handle_sched_pickdeck(
    callback: CallbackQuery,
    card_gateway: FromDishka[AnkiClient | MochiClient],
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
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
        deck_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"✅ {name}"
                        if backend_id == profile.vocab_scheduler_deck_id
                        else name,
                        callback_data=f"scheddeck:{i}",
                    )
                ]
                for i, (name, backend_id) in enumerate(decks)
            ]
        )
        await callback.message.reply("Choose the deck for daily vocab:", reply_markup=deck_keyboard)


@settings_router.callback_query(F.data.startswith("scheddeck:"))
async def handle_sched_deck_callback(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = callback.from_user.id
    decks = _waiting_deck.get(user_id)
    if not decks:
        await callback.answer("Session expired. Tap 'Scheduler deck' again.")
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

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
    updated = _update_profile(profile, vocab_scheduler_deck_id=backend_id)
    await profile_repo.save(updated)
    await callback.answer("✅ Deck set")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _schedule_text(updated), parse_mode="HTML", reply_markup=_schedule_keyboard(updated)
        )


@settings_router.message(lambda msg: msg.from_user is not None and msg.from_user.id in _editing)
async def handle_field_input(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    vocab_pool_repo: FromDishka[VocabPoolRepository],
    refill_service: FromDishka[VocabRefillService],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None or not message.text:
        return
    user_id = message.from_user.id
    edit_state = _editing.get(user_id)
    if not edit_state:
        return
    field, return_submenu = edit_state
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.reply(complete_setup())
        _editing.pop(user_id, None)
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), telegram_id=user_id)
    parsed, error = _parse_value(field, message.text)
    if error:
        await message.reply(error, parse_mode="HTML")
        return
    _editing.pop(user_id, None)
    updated = _update_profile(profile, **{field: parsed})
    await profile_repo.save(updated)
    if field == "level" and str(profile.level).upper().replace(" ", "") != str(
        parsed
    ).upper().replace(" ", ""):
        cleared = await vocab_pool_repo.clear_pool(profile.id, str(profile.target_lang))
        if cleared:
            await message.reply(
                f"♻️ Vocab pool cleared ({cleared} cards) — refilling at {parsed} level…"
            )
            asyncio.create_task(refill_service._refill(updated))
    text, keyboard = _submenu_content(return_submenu, updated)
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)
