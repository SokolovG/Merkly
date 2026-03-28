import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import setup_dialogs
from dishka.integrations.aiogram import setup_dishka

from src.config import Settings
from src.container import create_container
from src.infrastructure.scheduler.reminders import setup_scheduler
from src.infrastructure.telegram.dialogs.onboarding import onboarding_dialog
from src.infrastructure.telegram.handlers.commands import router as commands_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    token = settings.telegram_token.get_secret_value()

    bot = Bot(token=token)  # noqa: S106
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Wire dishka FIRST — middleware must exist before routers are attached
    container = create_container()
    setup_dishka(container, dp, auto_inject=True)

    # Register routers and dialogs
    dp.include_router(commands_router)
    dp.include_router(onboarding_dialog)
    setup_dialogs(dp)

    # Start scheduler
    from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
    profile_repo = await container.get(JsonProfileRepository)
    scheduler = setup_scheduler(bot, profile_repo)
    scheduler.start()

    await bot.set_my_commands([
        BotCommand(command="start", description="Start or restart the bot"),
        BotCommand(command="session", description="Start today's language lesson"),
        BotCommand(command="vocab", description="Goal-aware vocabulary cards (topic rotates)"),
        BotCommand(command="skip", description="Alias for /vocab"),
        BotCommand(command="settings", description="Update your profile"),
        BotCommand(command="help", description="Show available commands"),
    ])
    logger.info("Bot started. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
