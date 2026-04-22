"""In-memory Storage implementation — useful for tests and local dev without Redis."""

import asyncio
import time
from typing import Any

from backend.src.application.ports.storage import Storage
from backend.src.infrastructure.constants import SESSION_TTL


class _Entry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int | None) -> None:
        self.value = value
        self.expires_at: float | None = (time.monotonic() + ttl) if ttl is not None else None

    def is_expired(self) -> bool:
        return self.expires_at is not None and time.monotonic() > self.expires_at

    def remaining_ttl(self) -> int | None:
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.monotonic()
        return max(0, int(remaining))


class InMemoryStorage(Storage):
    """Thread-safe via asyncio (single-threaded event loop); not process-safe."""

    def __init__(self, default_ttl: int = SESSION_TTL) -> None:
        self._store: dict[str, _Entry] = {}
        self._counters: dict[str, int] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.is_expired():
                self._store.pop(key, None)
                return None
            return entry.value

    async def get_remaining_ttl(self, key: str) -> int | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.is_expired():
                return None
            return entry.remaining_ttl()

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        async with self._lock:
            self._store[key] = _Entry(value, ttl if ttl is not None else self._default_ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def expire(self, key: str, ttl: int) -> None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None and not entry.is_expired():
                entry.expires_at = time.monotonic() + ttl

    async def incr(self, key: str) -> int:
        async with self._lock:
            val = self._counters.get(key, 0) + 1
            self._counters[key] = val
            return val

    async def incr_with_expire(self, key: str, ttl: int) -> int:
        async with self._lock:
            val = self._counters.get(key, 0) + 1
            self._counters[key] = val
            # Mirror Redis: only set expire on first increment
            if val == 1:
                self._store[key] = _Entry({"_counter": val}, ttl)
            return val
