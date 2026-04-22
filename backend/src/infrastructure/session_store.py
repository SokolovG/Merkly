"""High-level session state manager built on the generic Storage port.

Key scheme:
  session:{session_id}    → full session dict, TTL SESSION_TTL
  user_session:{user_id}  → {"session_id": str}, TTL SESSION_TTL
"""

from backend.src.application.ports.storage import Storage
from backend.src.infrastructure.constants import SESSION_TTL


class RedisSessionStore:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def save(self, session: dict, user_id: str) -> None:
        """Persist session and update the per-user active-session index."""
        session_id: str = session["session_id"]
        await self._storage.set(f"session:{session_id}", session, ttl=SESSION_TTL)
        await self._storage.set(
            f"user_session:{user_id}", {"session_id": session_id}, ttl=SESSION_TTL
        )

    async def get(self, session_id: str) -> dict | None:
        """Return parsed session dict, or None if expired/missing."""
        return await self._storage.get(f"session:{session_id}")

    async def delete(self, session_id: str, user_id: str) -> None:
        """Remove session and its user index entry."""
        await self._storage.delete(f"session:{session_id}")
        await self._storage.delete(f"user_session:{user_id}")

    async def get_active_session_id(self, user_id: str) -> str | None:
        """Return the session_id for the user's active session, or None."""
        data = await self._storage.get(f"user_session:{user_id}")
        if data is None:
            return None
        return data.get("session_id")
