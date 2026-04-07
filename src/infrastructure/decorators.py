import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any

from aiogram.client.bot import T


def retry(
    max_attempts: int, backoff: float, max_backoff: float = 30.0
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    wait = min(backoff * (2**attempt), max_backoff)
                    await asyncio.sleep(wait)

        return wrapper

    return decorator
