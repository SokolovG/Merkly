import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dishka.integrations.aiogram import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.agent.core import LessonAgent
from src.application.listening_service import ListeningAgent
from src.config import Settings
from src.dependencies import create_container
from src.infrastructure.logging_config import configure_structlog
from src.infrastructure.scheduler.reminders import setup_scheduler
from src.infrastructure.telegram.commands import setup_bot

logger = structlog.get_logger(__name__)


async def main() -> None:
    settings = Settings()  # type: ignore
    configure_structlog(settings.DEBUG)

    bot = Bot(token=settings.TELEGRAM_TOKEN.get_secret_value())  # noqa: S106
    dp = Dispatcher(storage=MemoryStorage())

    container = create_container()
    setup_dishka(container, dp, auto_inject=True)

    await setup_bot(dp, bot)

    session_factory = await container.get(async_sessionmaker[AsyncSession])
    agent = await container.get(LessonAgent)
    listening_service = await container.get(ListeningAgent)
    scheduler = setup_scheduler(bot, session_factory, agent, listening_service)
    scheduler.start()

    logger.info("bot_started", mode="polling")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
