from abc import ABC, abstractmethod
from typing import Any


class Storage(ABC):
    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_remaining_ttl(self, key: str) -> int | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> None: ...

    @abstractmethod
    async def incr(self, key: str) -> int: ...

    @abstractmethod
    async def incr_with_expire(self, key: str, ttl: int) -> int: ...
