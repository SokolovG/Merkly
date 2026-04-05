import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dishka.integrations.aiogram import setup_dishka

from src.application.agent.core import LessonAgent
from src.config import Settings
from src.container import create_container
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
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
    bot = Bot(token=settings.telegram_token.get_secret_value())  # noqa: S106
    dp = Dispatcher(storage=MemoryStorage())

    container = create_container()
    setup_dishka(container, dp, auto_inject=True)

    await setup_bot(dp, bot)

    profile_repo = await container.get(JsonProfileRepository)
    agent = await container.get(LessonAgent)
    scheduler = setup_scheduler(bot, profile_repo, agent)
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

# TODO: Add listening lessons(fetch podcats, cut it)
# TODO: Add strategy for learning
# TODO: Add tool for computer vision - after writing or text in TG or photo(fetch data from photo)
# TODO: Maybe: Separate tg bot from backend, move it to frontend dir, make it just one of all front
# ports(need to change models...)
# TODO: Delete hardcode, make intefraces(for postgres, and more)
