import re
from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Const, Format

from src.infrastructure.telegram.handlers.onboarding_finish import save_profile_on_confirm
from src.infrastructure.telegram.states import OnboardingSG


# ── target language (buttons only — fixed set) ────────────────────────────────

async def on_target_lang(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["target_lang"] = button.widget_id
    await manager.next()


# ── level ──────────────────────────────────────────────────────────────────────

async def on_level(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["level"] = button.widget_id
    await manager.next()


async def on_level_text(message: Message, widget: Any, manager: DialogManager, value: str) -> None:
    manager.dialog_data["level"] = value.strip()
    await manager.next()


# ── goal ───────────────────────────────────────────────────────────────────────

async def on_goal(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["goal"] = button.widget_id
    await manager.next()


async def on_goal_text(message: Message, widget: Any, manager: DialogManager, value: str) -> None:
    manager.dialog_data["goal"] = value.strip()
    await manager.next()


# ── native language ────────────────────────────────────────────────────────────

async def on_native_lang(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["native_lang"] = button.widget_id
    await manager.next()


async def on_native_lang_text(
    message: Message, widget: Any, manager: DialogManager, value: str
) -> None:
    # Accept full name ("Turkish") or code ("tr") — store lowercase, max 20 chars
    manager.dialog_data["native_lang"] = value.strip().lower()[:20]
    await manager.next()


# ── session minutes ────────────────────────────────────────────────────────────

async def on_minutes(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["session_minutes"] = int(button.widget_id.replace("min_", ""))
    await manager.next()


async def on_minutes_text(
    message: Message, widget: Any, manager: DialogManager, value: str
) -> None:
    try:
        mins = int(value.strip())
        if mins < 5 or mins > 180:
            raise ValueError
        manager.dialog_data["session_minutes"] = mins
        await manager.next()
    except ValueError:
        await message.answer("Please enter a number between 5 and 180, e.g. 25")


# ── reminder ───────────────────────────────────────────────────────────────────

async def on_reminder(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    manager.dialog_data["reminder_enabled"] = button.widget_id == "remind_yes"
    if button.widget_id == "remind_yes":
        await manager.next()
    else:
        await manager.switch_to(OnboardingSG.confirm)


async def on_reminder_time(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    raw = button.widget_id[1:]  # strip leading "t"
    manager.dialog_data["reminder_time"] = raw[:2] + ":" + raw[2:]
    await manager.next()


async def on_custom_reminder_time(
    message: Message, widget: Any, manager: DialogManager, value: str
) -> None:
    value = value.strip()
    if re.match(r"^\d{1,2}:\d{2}$", value):
        h, m = value.split(":")
        manager.dialog_data["reminder_time"] = f"{int(h):02d}:{m}"
        await manager.next()
    else:
        await message.answer("Please use HH:MM format, e.g. 14:30")


async def on_utc(callback: CallbackQuery, button: Any, manager: DialogManager) -> None:
    raw = button.widget_id[3:]  # strip "utc"
    manager.dialog_data["utc_offset"] = int(raw.replace("m", "-"))
    await manager.switch_to(OnboardingSG.confirm)


# ── dialog ─────────────────────────────────────────────────────────────────────

onboarding_dialog = Dialog(
    Window(
        Const("Welcome! 👋\n\nWhich language do you want to learn?"),
        Row(
            Button(Const("🇩🇪 German"), id="de", on_click=on_target_lang),
            Button(Const("🇬🇧 English"), id="en", on_click=on_target_lang),
        ),
        Row(
            Button(Const("🇪🇸 Spanish"), id="es", on_click=on_target_lang),
            Button(Const("🇫🇷 French"), id="fr", on_click=on_target_lang),
        ),
        Row(
            Button(Const("🇮🇹 Italian"), id="it", on_click=on_target_lang),
            Button(Const("🇧🇷 Portuguese"), id="pt", on_click=on_target_lang),
        ),
        state=OnboardingSG.target_lang,
    ),
    Window(
        Const("What is your current level?\n\nPick one or type your own (e.g. B1+, B2-):"),
        Row(
            Button(Const("A1"), id="A1", on_click=on_level),
            Button(Const("A2"), id="A2", on_click=on_level),
            Button(Const("B1"), id="B1", on_click=on_level),
        ),
        Row(
            Button(Const("B2"), id="B2", on_click=on_level),
            Button(Const("C1"), id="C1", on_click=on_level),
            Button(Const("C2"), id="C2", on_click=on_level),
        ),
        TextInput(id="level_input", type_factory=str, on_success=on_level_text),
        state=OnboardingSG.level,
    ),
    Window(
        Const("Why are you learning this language?\n\nPick one or describe your goal:"),
        Row(
            Button(Const("✈️ Travel"), id="travel", on_click=on_goal),
            Button(Const("💼 Work"), id="work", on_click=on_goal),
        ),
        Row(
            Button(Const("💬 Conversation"), id="conversation", on_click=on_goal),
            Button(Const("📚 General"), id="general", on_click=on_goal),
        ),
        Row(
            Button(Const("🎓 Study / Uni"), id="study", on_click=on_goal),
        ),
        TextInput(id="goal_input", type_factory=str, on_success=on_goal_text),
        state=OnboardingSG.goal,
    ),
    Window(
        Const("What is your native language?\n\nPick one or type it (e.g. Turkish, Arabic, tr, ar):"),
        Row(
            Button(Const("🇬🇧 English"), id="en", on_click=on_native_lang),
            Button(Const("🇷🇺 Russian"), id="ru", on_click=on_native_lang),
        ),
        Row(
            Button(Const("🇺🇦 Ukrainian"), id="uk", on_click=on_native_lang),
            Button(Const("🇩🇪 German"), id="de", on_click=on_native_lang),
        ),
        Row(
            Button(Const("🇪🇸 Spanish"), id="es", on_click=on_native_lang),
            Button(Const("🇫🇷 French"), id="fr", on_click=on_native_lang),
        ),
        TextInput(id="native_lang_input", type_factory=str, on_success=on_native_lang_text),
        state=OnboardingSG.native_lang,
    ),
    Window(
        Const("How long should each session be?\n\nPick one or type your own (e.g. 25):"),
        Row(
            Button(Const("15 min"), id="min_15", on_click=on_minutes),
            Button(Const("30 min"), id="min_30", on_click=on_minutes),
            Button(Const("60 min"), id="min_60", on_click=on_minutes),
        ),
        TextInput(id="minutes_input", type_factory=str, on_success=on_minutes_text),
        state=OnboardingSG.session_minutes,
    ),
    Window(
        Const("Would you like a daily reminder to practice?"),
        Row(
            Button(Const("Yes, remind me"), id="remind_yes", on_click=on_reminder),
            Button(Const("No thanks"), id="remind_no", on_click=on_reminder),
        ),
        state=OnboardingSG.reminder,
    ),
    Window(
        Const("What time should I remind you?\n\nPick a time or type your own (e.g. 14:30):"),
        Row(
            Button(Const("08:00"), id="t0800", on_click=on_reminder_time),
            Button(Const("09:00"), id="t0900", on_click=on_reminder_time),
            Button(Const("10:00"), id="t1000", on_click=on_reminder_time),
        ),
        Row(
            Button(Const("11:00"), id="t1100", on_click=on_reminder_time),
            Button(Const("12:00"), id="t1200", on_click=on_reminder_time),
            Button(Const("18:00"), id="t1800", on_click=on_reminder_time),
        ),
        Row(
            Button(Const("20:00"), id="t2000", on_click=on_reminder_time),
            Button(Const("21:00"), id="t2100", on_click=on_reminder_time),
        ),
        TextInput(id="custom_time", type_factory=str, on_success=on_custom_reminder_time),
        state=OnboardingSG.reminder_time,
    ),
    Window(
        Const("What is your UTC offset?"),
        Row(
            Button(Const("UTC-5"), id="utcm5", on_click=on_utc),
            Button(Const("UTC+0"), id="utc0", on_click=on_utc),
            Button(Const("UTC+1"), id="utc1", on_click=on_utc),
        ),
        Row(
            Button(Const("UTC+2"), id="utc2", on_click=on_utc),
            Button(Const("UTC+3"), id="utc3", on_click=on_utc),
            Button(Const("UTC+4"), id="utc4", on_click=on_utc),
        ),
        state=OnboardingSG.utc_offset,
    ),
    Window(
        Format(
            "All set! Here's your profile:\n\n"
            "🌍 Learning: {dialog_data[target_lang]}\n"
            "📊 Level: {dialog_data[level]}\n"
            "🎯 Goal: {dialog_data[goal]}\n"
            "🗣 Native language: {dialog_data[native_lang]}\n"
            "⏱ Session: {dialog_data[session_minutes]} min\n\n"
            "Tap below to save and start!"
        ),
        Button(Const("✅ Save Profile"), id="save", on_click=save_profile_on_confirm),
        state=OnboardingSG.confirm,
    ),
)
