from datetime import UTC, datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.application.agent.prompts import lang_name
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository

_FLAG: dict[str, str] = {
    "de": "🇩🇪", "en": "🇬🇧", "es": "🇪🇸", "fr": "🇫🇷", "it": "🇮🇹", "pt": "🇧🇷",
    "ru": "🇷🇺", "ar": "🇸🇦", "zh": "🇨🇳",
}


async def send_reminders(bot: Bot, profile_repo: JsonProfileRepository) -> None:
    profiles = await profile_repo.all_with_reminders()
    now_utc = datetime.now(UTC)

    for profile in profiles:
        try:
            user_time = now_utc + timedelta(hours=profile.utc_offset)
            current_hhmm = user_time.strftime("%H:%M")

            if current_hhmm == profile.reminder_time:
                flag = _FLAG.get(profile.target_lang, "🌍")
                name = lang_name(profile.target_lang)
                await bot.send_message(
                    chat_id=profile.telegram_id,
                    text=(
                        f"Hey! {flag}\n\n"
                        f"Time for your daily {name} practice.\n"
                        "Type /session to start or /skip for quick vocabulary."
                    ),
                )
        except Exception:
            pass  # Don't crash the scheduler if one message fails


def setup_scheduler(bot: Bot, profile_repo: JsonProfileRepository) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="cron",
        minute="*",  # Check every minute, compare HH:MM inside
        kwargs={"bot": bot, "profile_repo": profile_repo},
    )
    return scheduler
