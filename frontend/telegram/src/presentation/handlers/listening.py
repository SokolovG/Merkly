import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka

from src.infrastructure.backend_client import BackendClient
from src.presentation import messages
from src.presentation.handlers.common import PLATFORM, contact_id
from src.presentation.handlers.session import _send_session_result

router = Router()
logger = structlog.get_logger(__name__)


@router.message(Command("listen"))
async def cmd_listen(message: Message, backend: FromDishka[BackendClient]) -> None:
    structlog.contextvars.clear_contextvars()
    cid = contact_id(message)
    structlog.contextvars.bind_contextvars(contact_id=cid)
    logger.info("cmd_listen")

    await message.answer(messages.preparing_lesson())
    try:
        result = await backend.start_listening_session(PLATFORM, cid)
    except Exception as e:
        await message.answer(messages.lesson_failed(str(e)))
        return

    await _send_session_result(message, result)
