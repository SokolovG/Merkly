from typing import Any

import msgspec
import structlog
from redis.asyncio import Redis

from backend.src.application.ports.storage import Storage
from backend.src.infrastructure.constants import LUA_INCR_AND_EXPIRE_SCRIPT, SESSION_TTL
from backend.src.infrastructure.exceptions import StorageError

logger = structlog.get_logger(__name__)


class RedisStorage(Storage):
    def __init__(self, redis_client: Redis) -> None:
        self.client = redis_client
        self.ttl = SESSION_TTL
        self._encoder = msgspec.json.Encoder()
        self._decoder = msgspec.json.Decoder()

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            data = await self.client.get(key)
            if data is None:
                return None
            decoded: dict[str, Any] = self._decoder.decode(data)
            return decoded
        except msgspec.DecodeError as err:
            logger.error("storage_decode_error", key=key, error=str(err))
            raise StorageError(f"Invalid data format for key {key!r}: {err}") from err
        except Exception as err:
            logger.error("storage_get_error", key=key, error=str(err))
            raise StorageError(f"Failed to get key {key!r}: {err}") from err

    async def get_remaining_ttl(self, key: str) -> int | None:
        try:
            ttl: int = await self.client.ttl(key)
            # Redis returns -2 for missing keys, -1 for keys with no expiry
            return ttl if ttl >= 0 else None
        except Exception as err:
            logger.error("storage_ttl_error", key=key, error=str(err))
            raise StorageError(f"Failed to get TTL for key {key!r}: {err}") from err

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            serialized = self._encoder.encode(value)
            await self.client.set(key, serialized, ex=ttl if ttl is not None else self.ttl)
        except msgspec.EncodeError as err:
            logger.error("storage_encode_error", key=key, error=str(err))
            raise StorageError(f"Failed to encode value for key {key!r}: {err}") from err
        except Exception as err:
            logger.error("storage_set_error", key=key, error=str(err))
            raise StorageError(f"Failed to set key {key!r}: {err}") from err

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except Exception as err:
            logger.error("storage_delete_error", key=key, error=str(err))
            raise StorageError(f"Failed to delete key {key!r}: {err}") from err

    async def expire(self, key: str, ttl: int) -> None:
        try:
            await self.client.expire(key, ttl)
        except Exception as err:
            logger.error("storage_expire_error", key=key, error=str(err))
            raise StorageError(f"Failed to set expiry on key {key!r}: {err}") from err

    async def incr(self, key: str) -> int:
        try:
            result: int = await self.client.incr(key)
            return result
        except Exception as err:
            logger.error("storage_incr_error", key=key, error=str(err))
            raise StorageError(f"Failed to increment key {key!r}: {err}") from err

    async def incr_with_expire(self, key: str, ttl: int) -> int:
        try:
            result: int = await self.client.eval(LUA_INCR_AND_EXPIRE_SCRIPT, 1, key, ttl)  # type: ignore
            return int(result)
        except Exception as err:
            logger.error("storage_incr_expire_error", key=key, error=str(err))
            raise StorageError(f"Failed to incr+expire key {key!r}: {err}") from err
