import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka

from src.domain.enums import ActivityType, Goal, Language, Level
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.telegram.messages import complete_setup

logger = logging.getLogger(__name__)

settings_router = Router()

# user_id → (field, return_submenu)
_editing: dict[int, tuple[str, str]] = {}

_ACTIVITY_LABELS = {
    ActivityType.READING: "📖 Reading",
    ActivityType.WRITING: "✍️ Writing",
    ActivityType.LISTENING: "🎧 Listening",
    ActivityType.VOCAB: "📚 Vocab",
}

_LANG_FLAGS = {
    "de": "🇩🇪",
    "en": "🇬🇧",
    "es": "🇪🇸",
    "fr": "🇫🇷",
    "it": "🇮🇹",
    "pt": "🇧🇷",
    "ru": "🇷🇺",
    "uk": "🇺🇦",
}

# Which submenu to return to after editing a field
_FIELD_SUBMENU = {
    "target_lang": "profile",
    "level": "profile",
    "goal": "profile",
    "native_lang": "profile",
    "session_minutes": "main",
    "reminder_time": "schedule",
    "utc_offset": "schedule",
    "vocab_scheduler_time": "schedule",
    "vocab_card_count": "main",
}

# Which submenu to return to after toggling
_TOGGLE_SUBMENU = {
    "reminder_enabled": "schedule",
}


def _lang_label(code: str) -> str:
    return f"{_LANG_FLAGS.get(str(code), '')} {str(code).upper()}"


# ── Text builders ────────────────────────────────────────────────────────────


def _main_text(profile) -> str:
    reminder_str = "off"
    if profile.reminder_enabled:
        sign = "+" if profile.utc_offset >= 0 else ""
        reminder_str = f"{profile.reminder_time} (UTC{sign}{profile.utc_offset})"
    strategy_parts = "  ·  ".join(
        f"{label.split()[1]} {'✅' if a in profile.learning_strategy else '☐'}"
        for a, label in _ACTIVITY_LABELS.items()
    )
    return (
        "⚙️ <b>Settings</b>\n\n"
        f"<b>Language</b>   {_lang_label(profile.target_lang)}\n"
        f"<b>Level</b>      {profile.level}\n"
        f"<b>Goal</b>       {profile.goal}\n"
        f"<b>Native</b>     {_lang_label(profile.native_lang)}\n\n"
        f"<b>Session</b>    {profile.session_minutes} min  ·  {profile.vocab_card_count} cards\n"
        f"<b>Reminder</b>   {reminder_str}\n\n"
        f"<b>Strategy</b>\n{strategy_parts}"
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
    return (
        "🔔 <b>Reminders & Schedule</b>\n\n"
        f"Reminder: {reminder_str}\n"
        f"⏰ Reminder time: {profile.reminder_time}\n"
        f"🌐 UTC offset: {profile.utc_offset:+}\n"
        f"📅 Vocab scheduler: {profile.vocab_scheduler_time}\n\n"
        "Tap a field to edit:"
    )


def _strategy_text(profile) -> str:
    lines = "\n".join(
        f"{label}: {'✅ ON' if a in profile.learning_strategy else '☐ OFF'}"
        for a, label in _ACTIVITY_LABELS.items()
    )
    return f"📋 <b>Strategy</b>\n\n{lines}\n\nTap to toggle:"


# ── Keyboard builders ────────────────────────────────────────────────────────


def _main_keyboard(profile) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profile", callback_data="settings:profile")],
            [
                InlineKeyboardButton(
                    text="🔔 Reminders & Schedule", callback_data="settings:schedule"
                )
            ],
            [InlineKeyboardButton(text="📋 Strategy", callback_data="settings:strategy")],
            [
                InlineKeyboardButton(
                    text=f"⏱ Session: {profile.session_minutes} min",
                    callback_data="set:session_minutes",
                ),
                InlineKeyboardButton(
                    text=f"🃏 Cards: {profile.vocab_card_count}",
                    callback_data="set:vocab_card_count",
                ),
            ],
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
                    text=f"📅 Vocab scheduler: {profile.vocab_scheduler_time}",
                    callback_data="set:vocab_scheduler_time",
                )
            ],
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
    "session_minutes": "Session duration in minutes (5–180):",
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
        try:
            return Level(value.upper()), None
        except ValueError:
            return value, None  # accept custom levels like "B1+"
    if field == "goal":
        try:
            return Goal(value.lower()), None
        except ValueError:
            return None, "Unknown goal. Use: <code>travel work conversation general study</code>"
    if field == "session_minutes":
        try:
            n = int(value)
            if not 5 <= n <= 180:
                raise ValueError
            return n, None
        except ValueError:
            return None, "Enter a number between 5 and 180."
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
    if message.from_user is None:
        return
    profile = await profile_repo.get(message.from_user.id)
    if not profile:
        await message.reply(complete_setup())
        return
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
    submenu = (callback.data or "").split(":", 1)[1]
    profile = await profile_repo.get(callback.from_user.id)
    if not profile:
        await callback.answer("Profile not found.")
        return
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


@settings_router.callback_query(F.data.startswith("settoggle:"))
async def handle_toggle(
    callback: CallbackQuery,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    field = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await callback.answer("Profile not found.")
        return

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


@settings_router.message(lambda msg: msg.from_user is not None and msg.from_user.id in _editing)
async def handle_field_input(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
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
    parsed, error = _parse_value(field, message.text)
    if error:
        await message.reply(error, parse_mode="HTML")
        return
    _editing.pop(user_id, None)
    updated = _update_profile(profile, **{field: parsed})
    await profile_repo.save(updated)
    text, keyboard = _submenu_content(return_submenu, updated)
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)
