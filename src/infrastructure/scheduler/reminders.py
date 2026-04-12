from datetime import UTC, datetime, timedelta
from html import escape

import structlog
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.application.agent.core import LessonAgent
from src.application.agent.prompts import lang_name
from src.application.vocab_refill_service import VocabRefillService
from src.domain.constants import LANGUAGE_FLAGS
from src.domain.entities import VocabCard
from src.domain.enums import ActivityType
from src.infrastructure.database.repositories import ProfileRepository
from src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository

logger = structlog.get_logger(__name__)


async def send_reminders(bot: Bot, session_factory: async_sessionmaker) -> None:
    logger.info("scheduler_job_start", job="send_reminders")
    async with session_factory() as session:
        profile_repo = ProfileRepository(session)
        profiles = await profile_repo.all_with_reminders()

    now_utc = datetime.now(UTC)
    sent = 0

    for profile in profiles:
        try:
            user_time = now_utc + timedelta(hours=profile.utc_offset)
            current_hhmm = user_time.strftime("%H:%M")

            if current_hhmm == profile.reminder_time:
                flag = LANGUAGE_FLAGS.get(profile.target_lang, "🌍")
                name = lang_name(profile.target_lang)
                await bot.send_message(
                    chat_id=profile.messenger_id,
                    text=(
                        f"Hey! {flag}\n\n"
                        f"Time for your daily {name} practice.\n"
                        "Type /session to start or /vocab for quick vocabulary."
                    ),
                )
                sent += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="send_reminders", error=str(exc))
    logger.info("scheduler_job_end", job="send_reminders", users_processed=sent)


async def send_scheduled_vocab(
    bot: Bot,
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> None:
    logger.info("scheduler_job_start", job="send_scheduled_vocab")
    async with session_factory() as session:
        profile_repo = ProfileRepository(session)
        profiles = await profile_repo.all()

    now_utc = datetime.now(UTC)
    sent = 0

    for profile in profiles:
        if not profile.vocab_scheduler_enabled:
            continue
        try:
            user_time = now_utc + timedelta(hours=profile.utc_offset)
            if user_time.strftime("%H:%M") != profile.vocab_scheduler_time:
                continue

            async with session_factory() as session:
                pool_repo = VocabPoolRepository(session)
                pool_cards = await pool_repo.get_pool_cards(
                    profile.id, str(profile.target_lang), profile.vocab_card_count
                )
                if not pool_cards:
                    refill_service = VocabRefillService(agent=agent, repo=pool_repo)
                    await refill_service._refill(profile)
                    pool_cards = await pool_repo.get_pool_cards(
                        profile.id, str(profile.target_lang), profile.vocab_card_count
                    )
                if not pool_cards:
                    continue

                vocab_cards = [
                    VocabCard(
                        word=pc.word,
                        translation=pc.translation,
                        example_sentence=pc.example_sentence,
                        word_type=pc.word_type,
                        article=pc.article,
                    )
                    for pc in pool_cards
                ]
                deck_id = profile.vocab_scheduler_deck_id or profile.active_deck_id or None
                for vc in vocab_cards:
                    await agent._anki.create_card(vc, deck_id=deck_id)
                await pool_repo.mark_shown(profile.id, [pc.id for pc in pool_cards])

            card_list = "\n".join(
                f"• <b>{escape(c.word)}</b> — {escape(c.translation)}" for c in vocab_cards
            )
            await bot.send_message(
                chat_id=profile.messenger_id,
                text=f"🃏 <b>Daily vocab</b>\n\n{card_list}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="send_scheduled_vocab", error=str(exc))
    logger.info("scheduler_job_end", job="send_scheduled_vocab", users_processed=sent)


async def refill_all_pools(
    session_factory: async_sessionmaker,
    agent: LessonAgent,
) -> None:
    """Nightly job: silently top up vocab pools for all users with VOCAB in learning strategy."""
    logger.info("scheduler_job_start", job="refill_all_pools")
    async with session_factory() as session:
        profiles = await ProfileRepository(session).all()

    processed = 0
    for profile in profiles:
        if ActivityType.VOCAB not in profile.learning_strategy:
            continue
        try:
            async with session_factory() as session:
                pool_repo = VocabPoolRepository(session)
                refill_service = VocabRefillService(agent=agent, repo=pool_repo)
                await refill_service.refill_if_needed(profile)
            processed += 1
        except Exception as exc:
            logger.warning("scheduler_user_error", job="refill_all_pools", error=str(exc))
    logger.info("scheduler_job_end", job="refill_all_pools", users_processed=processed)


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
    scheduler.add_job(
        refill_all_pools,
        trigger="cron",
        hour=3,
        minute=0,
        kwargs={"session_factory": session_factory, "agent": agent},
    )
    return scheduler
