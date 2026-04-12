from typing import Any

import structlog
from aiogram import Bot
from aiogram.types import Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput

from src.config import Settings
from src.domain.enums import MessengerType
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.telegram.messages import (
    bug_report_prompt,
    bug_report_sent,
    bug_report_unsupported_file,
)
from src.infrastructure.telegram.states import BugSG

logger = structlog.get_logger(__name__)

_SUPPORTED_CONTENT_TYPES = {"text", "photo", "video", "document"}


async def on_bug_report(
    message: Message,
    widget: Any,
    manager: DialogManager,
) -> None:
    structlog.contextvars.clear_contextvars()

    container = manager.middleware_data["dishka_container"]
    profile_repo: ProfileRepository = await container.get(ProfileRepository)
    settings: Settings = await container.get(Settings)
    bot: Bot = await container.get(Bot)

    if message.from_user is None or message.from_user.id is None:
        return
    user_id = message.from_user.id
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.answer("Profile not found.")
        await manager.done()
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)

    username = message.from_user.username or "Unknown"
    header = f"🐛 Bug Report\nFrom: {user_id} (@{username})\n\n"

    # If Telegram and BUG_REPORT_CHAT_ID configured → forward to admin chat
    if profile.messenger_type == MessengerType.TELEGRAM and settings.BUG_REPORT_CHAT_ID:
        admin_chat_id = int(settings.BUG_REPORT_CHAT_ID)

        if message.text:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=header + message.text,
            )
        elif message.photo:
            await bot.send_photo(
                chat_id=admin_chat_id,
                photo=message.photo[-1].file_id,
                caption=header + (message.caption or ""),
            )
        elif message.video:
            await bot.send_video(
                chat_id=admin_chat_id,
                video=message.video.file_id,
                caption=header + (message.caption or ""),
            )
        elif message.document:
            doc = message.document
            if doc.mime_type and doc.mime_type.startswith("application/pdf"):
                await bot.send_document(
                    chat_id=admin_chat_id,
                    document=doc.file_id,
                    caption=header + (message.caption or ""),
                )
            else:
                await message.answer(bug_report_unsupported_file())
                return  # Stay in state
        else:
            await message.answer(bug_report_unsupported_file())
            return  # Stay in state

        await message.answer(bug_report_sent())
    else:
        # Fallback to GitHub
        issues_url = (
            f"{settings.GITHUB_REPO_URL}/issues/new"
            if settings.GITHUB_REPO_URL
            else "https://github.com"
        )
        await message.answer(f"Please file a report at: {issues_url}")

    await manager.done()


bug_report_dialog = Dialog(
    Window(
        MessageInput(on_bug_report),
        state=BugSG.reporting,
        getter=lambda **kwargs: {"text": bug_report_prompt()},
    )
)
