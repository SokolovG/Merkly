from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram_dialog import setup_dialogs

from src.infrastructure.telegram.dialogs.onboarding import onboarding_dialog
from src.infrastructure.telegram.handlers.commands import router as commands_router
from src.infrastructure.telegram.handlers.deck_commands import deck_router
from src.infrastructure.telegram.handlers.listening import router as listening_router
from src.infrastructure.telegram.handlers.settings_menu import settings_router
from src.infrastructure.telegram.handlers.word_capture import word_router


@dataclass(frozen=True)
class _Cmd:
    command: str
    description: str

    def to_bot_command(self) -> BotCommand:
        return BotCommand(command=self.command, description=self.description)


_COMMANDS = [
    _Cmd("start", "Start or restart the bot"),
    _Cmd("session", "Start today's language lesson"),
    _Cmd("listen", "Start a listening lesson from a podcast"),
    _Cmd("vocab", "Goal-aware vocabulary cards (topic rotates)"),
    _Cmd("repeat", "Review previously seen words (oldest first)"),
    _Cmd("settings", "Update your profile and scheduler"),
    _Cmd("newdeck", "Create a new deck in Anki/Mochi"),
    _Cmd("setdeck", "Pick your active deck"),
    _Cmd("help", "Show available commands"),
]


async def setup_bot(dp: Dispatcher, bot: Bot) -> None:
    """Register all routers, dialogs, and bot commands."""
    # Router order matters: word_router MUST be first (intercepts + before dialogs)
    dp.include_router(word_router)
    dp.include_router(deck_router)
    dp.include_router(settings_router)
    dp.include_router(listening_router)
    dp.include_router(commands_router)
    dp.include_router(onboarding_dialog)
    setup_dialogs(dp)

    await bot.set_my_commands([cmd.to_bot_command() for cmd in _COMMANDS])
