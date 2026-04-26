import msgspec

from backend.src.application.ports.session_store import SessionStore
from backend.src.application.ports.storage import Storage
from backend.src.domain.session import SessionState
from backend.src.infrastructure.constants import SESSION_TTL


class SessionStoreImpl(SessionStore):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def save(self, session: SessionState, user_id: str) -> None:
        """Persist session and update the per-user active-session index."""
        payload = msgspec.json.decode(msgspec.json.encode(session))
        await self._storage.set(f"session:{session.session_id}", payload, ttl=SESSION_TTL)
        await self._storage.set(
            f"user_session:{user_id}", {"session_id": session.session_id}, ttl=SESSION_TTL
        )

    async def get(self, session_id: str) -> SessionState | None:
        """Return parsed SessionState, or None if expired/missing."""
        data = await self._storage.get(f"session:{session_id}")
        if data is None:
            return None
        return msgspec.convert(data, SessionState)

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
