"""/settings handler — thin I/O layer.

Reads and writes profile via BackendClient (PATCH /profiles/{user_id}).
All reminder scheduling (next_reminder_at) is computed server-side.
"""

import re

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient, ProfileResponse
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM
from src.presentation.handlers.common import contact_id as get_contact_id

router = Router()
logger = structlog.get_logger(__name__)

# telegram_user_id → field being edited
_editing: dict[int, str] = {}

_ACTIVITY_LABELS = {
    "reading": "📖 Reading",
    "writing": "✍️ Writing",
    "listening": "🎧 Listening",
    "vocab": "📚 Vocab",
}

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

_VALID_GOALS = {"travel", "work", "conversation", "general", "study"}

EPISODE_DURATION_OPTIONS = [3, 5, 10]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _lang_label(code: str) -> str:
    return code.upper()


async def _resolve(backend: BackendClient, telegram_user_id: int) -> ProfileResponse | None:
    identity = await backend.lookup_identity(PLATFORM, str(telegram_user_id))
    if not identity:
        return None
    return await backend.get_profile(identity.user_id)


def _parse_value(field: str, raw: str) -> tuple[object, str | None]:
    value = raw.strip()
    if field == "target_lang":
        val = value.lower()[:10]
        return val, None  # backend validates Language enum
    if field == "native_lang":
        return value.lower()[:20], None
    if field == "level":
        return value.upper().replace(" ", ""), None
    if field == "goal":
        if value.lower() not in _VALID_GOALS:
            return None, f"Unknown goal. Use: <code>{'  '.join(_VALID_GOALS)}</code>"
        return value.lower(), None
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


# ── Text builders ─────────────────────────────────────────────────────────────


def _main_text(p: ProfileResponse) -> str:
    strategy_parts = "  ·  ".join(
        f"{lbl.split()[1]} {'✅' if a in p.learning_strategy else '☐'}"
        for a, lbl in _ACTIVITY_LABELS.items()
    )
    return (
        "⚙️ <b>Settings</b>\n\n"
        f"<b>Language</b>   {p.target_lang.upper()}  ·  {p.level}  ·  {p.goal}\n"
        f"<b>Strategy</b>   {strategy_parts}"
    )


def _profile_text(p: ProfileResponse) -> str:
    return (
        "👤 <b>Profile</b>\n\n"
        f"🌍 Language: {p.target_lang.upper()}\n"
        f"📊 Level: {p.level}\n"
        f"🎯 Goal: {p.goal}\n"
        f"🗣 Native: {p.native_lang.upper()}\n\n"
        "Tap a field to edit:"
    )


def _schedule_text(p: ProfileResponse) -> str:
    if p.reminder_enabled:
        sign = "+" if p.utc_offset >= 0 else ""
        reminder_str = f"✅ {p.reminder_time} (UTC{sign}{p.utc_offset})"
    else:
        reminder_str = "❌ Off"
    sched_str = f"✅ {p.vocab_scheduler_time}" if p.vocab_scheduler_enabled else "❌ Off"
    return (
        "🔔 <b>Reminders & Schedule</b>\n\n"
        f"Reminder: {reminder_str}\n"
        f"⏰ Reminder time: {p.reminder_time}\n"
        f"🌐 UTC offset: {p.utc_offset:+}\n"
        f"📅 Vocab scheduler: {sched_str}\n\n"
        "Tap a field to edit:"
    )


def _strategy_text(p: ProfileResponse) -> str:
    lines = "\n".join(
        f"{lbl}: {'✅ ON' if a in p.learning_strategy else '☐ OFF'}"
        for a, lbl in _ACTIVITY_LABELS.items()
    )
    return f"📋 <b>Strategy</b>\n\n{lines}\n\nTap to toggle:"


def _session_text(p: ProfileResponse) -> str:
    return (
        "📊 <b>Session</b>\n\n"
        f"🃏 Vocab cards: {p.vocab_card_count}\n"
        f"❓ Questions: {p.question_count}\n"
        f"🎧 Listening clip: {p.episode_duration_min} min\n\n"
        "Tap a field to edit:"
    )


# ── Keyboard builders ─────────────────────────────────────────────────────────


def _main_keyboard(_p: ProfileResponse) -> InlineKeyboardMarkup:
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


def _profile_keyboard(p: ProfileResponse) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🌍 Language: {p.target_lang.upper()}", callback_data="set:target_lang"
                )
            ],
            [InlineKeyboardButton(text=f"📊 Level: {p.level}", callback_data="set:level")],
            [InlineKeyboardButton(text=f"🎯 Goal: {p.goal}", callback_data="set:goal")],
            [
                InlineKeyboardButton(
                    text=f"🗣 Native: {p.native_lang.upper()}", callback_data="set:native_lang"
                )
            ],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _session_keyboard(p: ProfileResponse) -> InlineKeyboardMarkup:
    duration_options = [
        InlineKeyboardButton(
            text=f"{'✅ ' if p.episode_duration_min == n else ''}{n} min",
            callback_data=f"setpick:episode_duration_min:{n}",
        )
        for n in EPISODE_DURATION_OPTIONS
    ]
    question_options = [
        InlineKeyboardButton(
            text=f"{'✅ ' if p.question_count == n else ''}{n} questions",
            callback_data=f"setpick:question_count:{n}",
        )
        for n in (2, 3, 5)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🃏 Cards: {p.vocab_card_count}", callback_data="set:vocab_card_count"
                )
            ],
            question_options,
            duration_options,
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _schedule_keyboard(p: ProfileResponse) -> InlineKeyboardMarkup:
    reminder_label = "🔔 Reminder: ✅ ON" if p.reminder_enabled else "🔔 Reminder: ❌ OFF"
    sched_label = (
        "📅 Vocab scheduler: ✅ ON" if p.vocab_scheduler_enabled else "📅 Vocab scheduler: ❌ OFF"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=reminder_label, callback_data="settoggle:reminder_enabled")],
            [
                InlineKeyboardButton(
                    text=f"⏰ Reminder time: {p.reminder_time}", callback_data="set:reminder_time"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🌐 UTC: {p.utc_offset:+}", callback_data="set:utc_offset"
                )
            ],
            [
                InlineKeyboardButton(
                    text=sched_label, callback_data="settoggle:vocab_scheduler_enabled"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⏰ Scheduler time: {p.vocab_scheduler_time}",
                    callback_data="set:vocab_scheduler_time",
                )
            ],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _strategy_keyboard(p: ProfileResponse) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[
                [
                    InlineKeyboardButton(
                        text=f"{lbl}: {'✅ ON' if a in p.learning_strategy else '☐ OFF'}",
                        callback_data=f"settoggle:strategy_{a}",
                    )
                ]
                for a, lbl in _ACTIVITY_LABELS.items()
            ],
            [InlineKeyboardButton(text="← Back", callback_data="settings:main")],
        ]
    )


def _submenu_content(submenu: str, p: ProfileResponse) -> tuple[str, InlineKeyboardMarkup]:
    match submenu:
        case "profile":
            return _profile_text(p), _profile_keyboard(p)
        case "session":
            return _session_text(p), _session_keyboard(p)
        case "schedule":
            return _schedule_text(p), _schedule_keyboard(p)
        case "strategy":
            return _strategy_text(p), _strategy_keyboard(p)
        case _:
            return _main_text(p), _main_keyboard(p)


# ── Handlers ──────────────────────────────────────────────────────────────────


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None:
        return
    cid = get_contact_id(message)
    profile = await _resolve(backend, message.from_user.id)
    if not profile:
        await message.reply(messages.no_profile())
        return
    structlog.contextvars.bind_contextvars(user_id=profile.user_id, contact_id=cid)
    await message.reply(
        _main_text(profile), parse_mode="HTML", reply_markup=_main_keyboard(profile)
    )


@router.callback_query(F.data.startswith("settings:"))
async def handle_nav(
    callback: CallbackQuery,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    if callback.from_user is None:
        return
    submenu = (callback.data or "").split(":", 1)[1]
    profile = await _resolve(backend, callback.from_user.id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    structlog.contextvars.bind_contextvars(user_id=profile.user_id)
    text, keyboard = _submenu_content(submenu, profile)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("set:"))
async def handle_edit_button(callback: CallbackQuery) -> None:
    field = (callback.data or "").split(":", 1)[1]
    if field not in _FIELD_PROMPTS:
        await callback.answer("Unknown field.")
        return
    if callback.from_user is None:
        return
    _editing[callback.from_user.id] = field
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(_FIELD_PROMPTS[field], parse_mode="HTML")


@router.callback_query(F.data.startswith("setpick:"))
async def handle_pick(
    callback: CallbackQuery,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3 or callback.from_user is None:
        await callback.answer("Invalid.")
        return
    _, field, raw_value = parts
    try:
        value = int(raw_value)
    except ValueError:
        await callback.answer("Invalid value.")
        return
    profile = await _resolve(backend, callback.from_user.id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    structlog.contextvars.bind_contextvars(user_id=profile.user_id)
    updated = await backend.update_profile(profile.user_id, **{field: value})
    await callback.answer(f"✅ Set to {value}")
    submenu = _FIELD_SUBMENU.get(field, "main")
    text, keyboard = _submenu_content(submenu, updated)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("settoggle:"))
async def handle_toggle(
    callback: CallbackQuery,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    if callback.from_user is None:
        return
    field = (callback.data or "").split(":", 1)[1]
    profile = await _resolve(backend, callback.from_user.id)
    if not profile:
        await callback.answer("Profile not found.")
        return
    structlog.contextvars.bind_contextvars(user_id=profile.user_id)

    if field.startswith("strategy_"):
        activity = field[len("strategy_") :]
        strategy = list(profile.learning_strategy)
        if activity in strategy:
            if len(strategy) <= 1:
                await callback.answer("Keep at least one activity enabled.")
                return
            strategy.remove(activity)
        else:
            strategy.append(activity)
        updated = await backend.update_profile(profile.user_id, learning_strategy=strategy)
        return_submenu = "strategy"
    else:
        current = getattr(profile, field, False)
        updated = await backend.update_profile(profile.user_id, **{field: not current})
        return_submenu = "schedule"

    await callback.answer()
    text, keyboard = _submenu_content(return_submenu, updated)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(lambda msg: msg.from_user is not None and msg.from_user.id in _editing)
async def handle_field_input(
    message: Message,
    backend: FromDishka[BackendClient],
) -> None:
    structlog.contextvars.clear_contextvars()
    if message.from_user is None or not message.text:
        return
    user_id = message.from_user.id
    field = _editing.get(user_id)
    if not field:
        return

    parsed, error = _parse_value(field, message.text)
    if error:
        await message.reply(error, parse_mode="HTML")
        return

    _editing.pop(user_id, None)
    profile = await _resolve(backend, user_id)
    if not profile:
        await message.reply(messages.no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=profile.user_id)
    updated = await backend.update_profile(profile.user_id, **{field: parsed})
    return_submenu = _FIELD_SUBMENU.get(field, "main")
    text, keyboard = _submenu_content(return_submenu, updated)
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)
