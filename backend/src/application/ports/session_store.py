from abc import ABC, abstractmethod

from backend.src.domain.session import SessionState


class SessionStore(ABC):
    @abstractmethod
    async def save(self, session: SessionState, user_id: str) -> None: ...

    @abstractmethod
    async def get(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    async def delete(self, session_id: str, user_id: str) -> None: ...

    @abstractmethod
    async def get_active_session_id(self, user_id: str) -> str | None: ...
