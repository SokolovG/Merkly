from datetime import UTC, datetime, timedelta
from html import escape

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.application.agent.core import LessonAgent
from src.application.agent.prompts import lang_name
from src.domain.constants import LANGUAGE_FLAGS
from src.infrastructure.database.repositories import ProfileRepository


async def send_reminders(bot: Bot, session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        profile_repo = ProfileRepository(session)
        profiles = await profile_repo.all_with_reminders()

    now_utc = datetime.now(UTC)

    for profile in profiles:
        try:
            user_time = now_utc + timedelta(hours=profile.utc_offset)
            current_hhmm = user_time.strftime("%H:%M")

            if current_hhmm == profile.reminder_time:
                flag = LANGUAGE_FLAGS.get(profile.target_lang, "🌍")
                name = lang_name(profile.target_lang)
                await bot.send_message(
                    chat_id=profile.telegram_id,
                    text=(
                        f"Hey! {flag}\n\n"
                        f"Time for your daily {name} practice.\n"
                        "Type /session to start or /vocab for quick vocabulary."
                    ),
                )
        except Exception:
            pass  # Don't crash the scheduler if one message fails


async def send_scheduled_vocab(
    bot: Bot,
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> None:
    async with session_factory() as session:
        profile_repo = ProfileRepository(session)
        profiles = await profile_repo.all()

    now_utc = datetime.now(UTC)

    for profile in profiles:
        if not profile.vocab_scheduler_enabled:
            continue
        try:
            user_time = now_utc + timedelta(hours=profile.utc_offset)
            if user_time.strftime("%H:%M") != profile.vocab_scheduler_time:
                continue
            topic_name, cards = await agent.topic_vocab_lesson(
                level=profile.level,
                goal=profile.goal,
                native_lang=profile.native_lang,
                target_lang=profile.target_lang,
                recent_topics=[],
                count=profile.vocab_card_count,
            )
            if cards:
                card_list = "\n".join(
                    f"• <b>{escape(c.word)}</b> — {escape(c.translation)}" for c in cards
                )
                await bot.send_message(
                    chat_id=profile.telegram_id,
                    text=f"🃏 <b>Daily vocab: {escape(topic_name)}</b>\n\n{card_list}",
                    parse_mode="HTML",
                )
        except Exception:
            pass


def setup_scheduler(
    bot: Bot,
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="cron",
        minute="*",
        kwargs={"bot": bot, "session_factory": session_factory},
    )
    scheduler.add_job(
        send_scheduled_vocab,
        trigger="cron",
        minute="*",
        kwargs={"bot": bot, "session_factory": session_factory, "agent": agent},
    )
    return scheduler
