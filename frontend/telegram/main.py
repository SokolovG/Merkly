import asyncio
import logging

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dishka.integrations.aiogram import setup_dishka

from src.config.di import build_container
from src.config.settings import TgSettings
from src.presentation.handlers.commands import catch_all_router
from src.presentation.handlers.commands import router as cmd_router
from src.presentation.handlers.listening import router as listen_router
from src.presentation.handlers.settings import router as settings_router
from src.presentation.handlers.word_capture import router as word_router


def configure_structlog(debug: bool) -> None:
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_bot(settings: TgSettings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Register routers: word_router before cmd_router (+ prefix must match before catch-all)
    dp.include_router(word_router)
    dp.include_router(listen_router)
    dp.include_router(settings_router)
    dp.include_router(cmd_router)
    dp.include_router(catch_all_router)  # must be last

    container = build_container(settings)
    setup_dishka(container=container, router=dp, auto_inject=True)

    return bot, dp


_BOT_COMMANDS = [
    BotCommand(command="session", description="Auto-start a lesson"),
    BotCommand(command="reading", description="Start a reading session"),
    BotCommand(command="listen", description="Start a listening session"),
    BotCommand(command="writing", description="Standalone writing task"),
    BotCommand(command="next", description="Skip current step, start new session activity"),
    BotCommand(command="lesson", description="Pick lesson type manually"),
    BotCommand(command="vocab", description="Vocabulary cards"),
    BotCommand(command="repeat", description="Review saved word history"),
    BotCommand(command="exit", description="Cancel the active session"),
    BotCommand(command="settings", description="Configure your profile and preferences"),
    BotCommand(command="help", description="Show help"),
]


async def main() -> None:
    settings = TgSettings()  # type: ignore
    configure_structlog(settings.DEBUG)

    bot, dp = setup_bot(settings)
    await bot.set_my_commands(_BOT_COMMANDS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
