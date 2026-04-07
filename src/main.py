import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dishka.integrations.aiogram import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.agent.core import LessonAgent
from src.config import Settings
from src.dependencies import create_container
from src.infrastructure.scheduler.reminders import setup_scheduler
from src.infrastructure.telegram.commands import setup_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()  # type: ignore
    bot = Bot(token=settings.TELEGRAM_TOKEN.get_secret_value())  # noqa: S106
    dp = Dispatcher(storage=MemoryStorage())

    container = create_container()
    setup_dishka(container, dp, auto_inject=True)

    await setup_bot(dp, bot)

    session_factory = await container.get(async_sessionmaker[AsyncSession])
    agent = await container.get(LessonAgent)
    scheduler = setup_scheduler(bot, session_factory, agent)
    scheduler.start()

    logger.info("Bot started. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())


# TODO: add intruduction in start(help texts, explain logic of bot)
# TODO: If the “thema” parameter is set to “study,”
# that doesn't mean all the words have to be related to university and so on.
# I'm teaching general language; individual words are useful, but not always
# TODO: rename/move prepare_lesson(its in AgentService/ListeningService)
# TODO: add reading/audio/writing pool like vocab pool
# TODO: Request Entity Too Large - podcast dont cuts
# TODO: whisper-1 is not a valid model name. Using base instead.
# TODO: Detected language 'en' with probability 1.00
